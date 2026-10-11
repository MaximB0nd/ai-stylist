import hashlib
import hmac
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import uuid


from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.dependencies import (
    get_ai_core_client,
    get_album_repository,
)
from app.db.repositories.album_repository import AlbumRepository
from app.services.generation_queue import enqueue_results as _download_and_store_results
from app.services.ai_core_client import AICoreClient

logger = logging.getLogger(__name__)

router = APIRouter()

# Whitelist pattern for object_key values coming from legacy callback.
# Must match: albums/<uuid>/look_NN.webp or sources/<uuid>/<uuid>/face.jpg etc.
_OBJECT_KEY_PATTERN = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9/_\-\.]{0,511}$"
)


# ---------------------------------------------------------------------------
# Pydantic schemas for incoming webhook payloads
# ---------------------------------------------------------------------------

class LegacyPhotoItem(BaseModel):
    """Single photo entry in the legacy callback payload."""

    order_index: int = Field(..., ge=0, le=9)
    object_key: str = Field(..., min_length=1, max_length=512)

    @field_validator("object_key")
    @classmethod
    def validate_object_key(cls, v: str) -> str:
        """Reject object_key values that could be path-traversal attempts."""
        if not _OBJECT_KEY_PATTERN.match(v):
            raise ValueError(
                f"object_key '{v}' contains invalid characters or path traversal sequences."
            )
        if ".." in v or v.startswith("/"):
            raise ValueError("object_key must not contain '..' or start with '/'.")
        return v


class LegacyCallbackPayload(BaseModel):
    """Validated body for POST /internal/generations/{id}/complete."""

    photos: List[LegacyPhotoItem] = Field(..., min_length=1, max_length=10)

    @field_validator("photos")
    @classmethod
    def unique_orders(cls, photos):
        if len({p.order_index for p in photos}) != len(photos):
            raise ValueError("Duplicate photo order_index")
        return photos



# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _verify_webhook_auth(
    raw_body: bytes,
    x_ai_core_timestamp: Optional[str] = None,
    x_ai_core_signature: Optional[str] = None,
    x_internal_token: Optional[str] = None,
) -> None:
    """Verify request authenticity using HMAC-SHA256 signature or service token."""
    # 1. HMAC-SHA256 verification (preferred by AI Core external contract)
    if x_ai_core_signature and x_ai_core_timestamp:
        try:
            ts = float(x_ai_core_timestamp)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid timestamp header.",
            )

        # Reject signatures older than 5 minutes (replay protection)
        now = time.time()
        if abs(now - ts) > 300:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook timestamp expired (drift > 300s).",
            )

        # Combine timestamp bytes with raw body bytes directly (safe against UnicodeDecodeError)
        message = f"{x_ai_core_timestamp}.".encode("utf-8") + raw_body
        expected_sig = hmac.new(
            settings.AI_CORE_WEBHOOK_SECRET.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, x_ai_core_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC-SHA256 signature.",
            )
        return

    # 2. Token-based verification (fallback for legacy AI callback contract)
    # NOTE: Static tokens have no replay protection — use HMAC path for new integrations.
    if x_internal_token:
        if hmac.compare_digest(settings.AI_CORE_SERVICE_TOKEN, x_internal_token):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal token.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing webhook authentication headers.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/ai-events",
    status_code=status.HTTP_200_OK,
    summary="AI Core Webhook Event Receiver",
    description="Receives progress and completion events from AI Core.",
)
async def handle_ai_core_event(
    request: Request,
    background_tasks: BackgroundTasks,
    x_ai_core_timestamp: Optional[str] = Header(None, alias="X-AI-Core-Timestamp"),
    x_ai_core_signature: Optional[str] = Header(None, alias="X-AI-Core-Signature"),
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
    album_repo: AlbumRepository = Depends(get_album_repository),
    ai_client: AICoreClient = Depends(get_ai_core_client),
) -> Dict[str, Any]:
    """Handle webhook notifications from AI Core."""
    raw_body = await request.body()
    _verify_webhook_auth(
        raw_body,
        x_ai_core_timestamp=x_ai_core_timestamp,
        x_ai_core_signature=x_ai_core_signature,
        x_internal_token=x_internal_token,
    )

    try:
        data = json.loads(raw_body)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    job_id_str = data.get("job_id") or data.get("generation_id")
    if not job_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing job_id or generation_id in payload.",
        )

    try:
        job_uuid = uuid.UUID(job_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID for job_id.",
        )

    # Find album by generation_id or ai_job_id
    album = await album_repo.get_by_generation_id(job_uuid)
    if not album and hasattr(album_repo, "get_by_ai_job_id"):
        album = await album_repo.get_by_ai_job_id(job_uuid)

    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Album not found for generation/job {job_uuid}",
        )

    event_status = data.get("status", "").upper()

    # Idempotency: already fully processed — no work needed
    if album.status in ("COMPLETED", "FAILED"):
        return {"status": "already_finalized", "album_id": str(album.id), "success": True}

    if event_status == "PROCESSING":
        # Atomically transition only if status is VALIDATING or QUEUED.
        # This prevents delayed/out-of-order PROCESSING events from regressing
        # DOWNLOADING, COMPLETED, or FAILED states.
        if hasattr(album_repo, "atomic_transition"):
            transitioned = await album_repo.atomic_transition(
                album.id,
                from_statuses=["VALIDATING", "QUEUED"],
                to_status="PROCESSING",
            )
            if not transitioned:
                logger.warning(
                    "Ignoring out-of-order PROCESSING event for album %s (current status=%s). "
                    "Event discarded to prevent regression.",
                    album.id, album.status,
                )
                return {"status": "out_of_order_ignored", "album_id": str(album.id)}
        else:
            _TERMINAL_OR_ADVANCED = {"DOWNLOADING", "COMPLETED", "FAILED"}
            if album.status in _TERMINAL_OR_ADVANCED:
                logger.warning(
                    "Ignoring out-of-order PROCESSING event for album %s (current status=%s). "
                    "Event discarded to prevent regression.",
                    album.id, album.status,
                )
                return {"status": "out_of_order_ignored", "album_id": str(album.id)}
            await album_repo.update_status(album.id, status="PROCESSING")
        return {"status": "ok", "album_id": str(album.id)}

    elif event_status == "FAILED":
        err_detail = data.get("error")
        err_msg = json.dumps(err_detail) if isinstance(err_detail, (dict, list)) else str(err_detail or "Generation failed")
        await album_repo.atomic_transition(
            album.id, ["VALIDATING", "QUEUED", "PROCESSING"], "FAILED", error_message=err_msg[:500]
        )
        return {"status": "failed", "album_id": str(album.id)}

    elif event_status == "COMPLETED":
        # Check if direct photos list is in payload (legacy contract)
        if "photos" in data and isinstance(data["photos"], list):
            if not data["photos"]:
                logger.warning("Empty photos list in legacy COMPLETED webhook for album %s", album.id)
                await album_repo.atomic_transition(
                    album.id, ["VALIDATING", "QUEUED", "PROCESSING"], "FAILED",
                    error_message="Received COMPLETED event with empty photos list",
                )
                return {"status": "failed", "error": "Empty photos list", "album_id": str(album.id)}
            try:
                payload = LegacyCallbackPayload.model_validate({"photos": data["photos"]})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            return await _accept_callback(album_repo, album, payload)

        # Only an unclaimed or expired lease may be acquired by this handler.
        claimed = await album_repo.atomic_claim_for_download(album.id)
        if claimed is None:
            # Another concurrent webhook handler already claimed it — this is a duplicate.
            logger.info(
                "Duplicate COMPLETED webhook for album %s. Skipping.",
                album.id,
            )
            return {"success": True, "album_id": str(album.id), "status": "duplicate_ignored"}

        # Persist the waiting state before acknowledgement; workers claim on dequeue.
        if not await album_repo.finish_work(album.id, claimed, status="DOWNLOADING"):
            return {"success": True, "album_id": str(album.id), "status": "duplicate_ignored"}
        background_tasks.add_task(
            _download_and_store_results,
            album_id=album.id,
            job_uuid=album.ai_job_id or job_uuid,
            ai_client=ai_client,
            token=None,
        )
        return {"success": True, "album_id": str(album.id)}

    return {"status": "ignored", "event_status": event_status}



@router.post(
    "/generations/{generation_id}/complete",
    status_code=status.HTTP_200_OK,
    summary="Legacy AI Module Webhook Callback",
    description="Backward-compatible endpoint for AI_MODULE_WEBHOOK_CALLBACK.md.",
)
async def legacy_complete_generation(
    generation_id: uuid.UUID,
    request: Request,
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
    album_repo: AlbumRepository = Depends(get_album_repository),
) -> Dict[str, Any]:
    """Support legacy callback format per AI_MODULE_WEBHOOK_CALLBACK.md.

    Security notes:
    - Authenticated via static X-Internal-Token (no replay protection — prefer HMAC webhook).
    - photos[].object_key is validated against a whitelist pattern to prevent
      path-traversal attacks or injection of foreign object keys.
    """
    raw_body = await request.body()
    _verify_webhook_auth(raw_body, x_internal_token=x_internal_token)

    # Parse and validate payload via Pydantic — rejects invalid object_key, missing fields, etc.
    try:
        payload = LegacyCallbackPayload.model_validate_json(raw_body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {exc}",
        )

    album = await album_repo.get_by_generation_id(generation_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or invalid generation_id.",
        )

    # Idempotency guard
    if album.status in ("COMPLETED", "FAILED"):
        return {"success": True, "album_id": str(album.id), "status": "already_finalized"}

    return await _accept_callback(album_repo, album, payload)


async def _accept_callback(album_repo, album, payload):
    photos_data = sorted([
        {"order_index": p.order_index, "object_key": p.object_key,
         "is_cover": p.order_index == 0, "is_favorite": False}
        for p in payload.photos
    ], key=lambda p: p["order_index"])
    try:
        outcome = await album_repo.persist_callback(album.id, photos_data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if outcome == "already_finalized":
        return {"success": True, "album_id": str(album.id), "status": outcome}
    token = await album_repo.atomic_claim_for_download(album.id)
    if token is not None and await album_repo.complete_with_photos(album.id, photos_data, token):
        return {"success": True, "album_id": str(album.id)}
    # Recovery consumes the persisted callback after the current lease expires/releases.
    return {"success": True, "album_id": str(album.id), "status": "accepted"}
