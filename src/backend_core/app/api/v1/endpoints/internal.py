import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import uuid


from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
import httpx
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.dependencies import (
    get_ai_core_client,
    get_album_repository,
    get_storage_service,
)
from app.db.repositories.album_repository import AlbumRepository
from app.db.session import AsyncSessionLocal
from app.services.ai_core_client import AICoreClient
from app.services.storage_service import StorageService

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

    order_index: int = Field(..., ge=0, le=99)
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

    photos: List[LegacyPhotoItem] = Field(..., min_length=1, max_length=50)


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
# Background download task — always uses a fresh DB session
# ---------------------------------------------------------------------------

async def _download_and_store_results(
    album_id: uuid.UUID,
    job_uuid: uuid.UUID,
    ai_client: AICoreClient,
) -> None:
    """Background task: fetch images from AI Core temp S3 in parallel,
    upload to permanent MinIO and persist to DB.

    Always creates its own AsyncSession because the request-scoped session
    is already closed by the time this background task runs.
    """
    # Import here to avoid circular dependency at module load time
    from app.services.storage_service import StorageService as _StorageService

    storage = _StorageService()

    try:
        job_details = await ai_client.get_job(job_uuid)
        results = job_details.get("results", [])

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            async def _download_and_upload_single(item: dict) -> dict:
                order_index = item["order_index"]
                download_url = item["download_url"]

                img_resp = await http_client.get(download_url)
                if img_resp.status_code != 200:
                    raise RuntimeError(
                        f"Failed to download image from AI Core at order {order_index}: HTTP {img_resp.status_code}"
                    )
                content = img_resp.content

                # Verify SHA256 checksum if provided.
                # A mismatch means the image is corrupt/tampered — abort the whole album.
                if item.get("checksum_sha256"):
                    expected_sha = item["checksum_sha256"].replace("sha256:", "")
                    actual_sha = hashlib.sha256(content).hexdigest()
                    if actual_sha != expected_sha:
                        raise RuntimeError(
                            f"SHA256 checksum mismatch for order {order_index}: "
                            f"expected {expected_sha}, got {actual_sha}. "
                            "Image may be corrupt or tampered."
                        )

                # Store in Permanent MinIO
                dest_key = f"albums/{album_id}/look_{order_index:02d}.webp"
                await storage.upload_bytes(dest_key, content, content_type="image/webp")

                return {
                    "order_index": order_index,
                    "object_key": dest_key,
                    "is_cover": (order_index == 0),
                    "is_favorite": False,
                }

            # Download and upload all images concurrently
            photos_data = await asyncio.gather(*[_download_and_upload_single(item) for item in results])
            photos_data = sorted(photos_data, key=lambda p: p["order_index"])

        # Always use a fresh session — the request-scoped session is already closed
        async with AsyncSessionLocal() as session:
            from app.db.repositories.album_repository import AlbumRepository as _Repo
            repo = _Repo(session=session)
            await repo.add_photos(album_id, list(photos_data))
            await repo.update_status(album_id, status="COMPLETED")

        # Acknowledge delivery to AI Core so it cleans up temporary S3
        try:
            await ai_client.acknowledge_results(job_uuid)
        except Exception as exc:
            logger.warning("Could not send ACK to AI Core for job %s: %s", job_uuid, exc)

        logger.info("Successfully processed and saved completed album %s in parallel", album_id)

    except Exception as exc:
        logger.exception("Failed to process completed job %s for album %s: %s", job_uuid, album_id, exc)
        # Always use a fresh session for error recording too
        try:
            async with AsyncSessionLocal() as session:
                from app.db.repositories.album_repository import AlbumRepository as _Repo
                repo = _Repo(session=session)
                await repo.update_status(
                    album_id,
                    status="FAILED",
                    error_message=f"Failed to download results: {exc}"[:500],
                )
        except Exception as db_exc:
            logger.exception(
                "Could not persist FAILED status for album %s after download error: %s",
                album_id,
                db_exc,
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
        await album_repo.update_status(album.id, status="PROCESSING")
        return {"status": "ok", "album_id": str(album.id)}

    elif event_status == "FAILED":
        err_detail = data.get("error")
        err_msg = json.dumps(err_detail) if isinstance(err_detail, (dict, list)) else str(err_detail or "Generation failed")
        await album_repo.update_status(album.id, status="FAILED", error_message=err_msg[:500])
        return {"status": "failed", "album_id": str(album.id)}

    elif event_status == "COMPLETED":
        # Check if direct photos list is in payload (legacy contract)
        if "photos" in data and isinstance(data["photos"], list):
            photos_data = [
                {
                    "order_index": p["order_index"],
                    "object_key": p["object_key"],
                    "is_cover": (p["order_index"] == 0),
                    "is_favorite": False,
                }
                for p in data["photos"]
            ]
            await album_repo.add_photos(album.id, photos_data)
            await album_repo.update_status(album.id, status="COMPLETED")
            return {"success": True, "album_id": str(album.id)}

        # Standard AI Core contract: atomically claim the download slot to prevent
        # race conditions when AI Core retries the webhook before we finish downloading.
        claimed = await album_repo.atomic_claim_for_download(album.id)
        if not claimed:
            # Another concurrent webhook handler already claimed it — this is a duplicate.
            logger.info(
                "Duplicate COMPLETED webhook for album %s (status was not PROCESSING). Skipping.",
                album.id,
            )
            return {"success": True, "album_id": str(album.id), "status": "duplicate_ignored"}

        # Only the "winner" of the atomic claim runs the background download
        background_tasks.add_task(
            _download_and_store_results,
            album_id=album.id,
            job_uuid=job_uuid,
            ai_client=ai_client,
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

    photos_data = [
        {
            "order_index": p.order_index,
            "object_key": p.object_key,
            "is_cover": (p.order_index == 0),
            "is_favorite": False,
        }
        for p in payload.photos
    ]

    await album_repo.add_photos(album.id, photos_data)
    await album_repo.update_status(album.id, status="COMPLETED")

    return {"success": True, "album_id": str(album.id)}
