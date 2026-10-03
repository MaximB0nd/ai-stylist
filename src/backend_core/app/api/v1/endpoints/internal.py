import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional
import uuid


from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
import httpx

from app.core.config import settings
from app.core.dependencies import (
    get_ai_core_client,
    get_album_repository,
    get_storage_service,
)
from app.db.repositories.album_repository import AlbumRepository
from app.services.ai_core_client import AICoreClient
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter()


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

        # Reject signatures older than 5 minutes
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


async def _download_and_store_results(
    album_id: uuid.UUID,
    job_uuid: uuid.UUID,
    album_repo: AlbumRepository,
    storage: StorageService,
    ai_client: AICoreClient,
) -> None:
    """Background task to fetch images from AI Core temp S3 in parallel, upload to permanent S3 and persist to DB."""
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

                # Verify SHA256 checksum if provided
                if item.get("checksum_sha256"):
                    expected_sha = item["checksum_sha256"].replace("sha256:", "")
                    actual_sha = hashlib.sha256(content).hexdigest()
                    if actual_sha != expected_sha:
                        logger.warning(
                            "Checksum mismatch for order %d: expected %s, got %s",
                            order_index,
                            expected_sha,
                            actual_sha,
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

            # Download and upload all 10 images concurrently (asyncio.gather)
            photos_data = await asyncio.gather(*[_download_and_upload_single(item) for item in results])
            photos_data.sort(key=lambda p: p["order_index"])

        # Persist photos to DB (using isolated session in production to prevent connection pool exhaustion)
        if hasattr(album_repo, "session") and album_repo.session is not None:
            from app.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                repo = AlbumRepository(session=session)
                await repo.add_photos(album_id, photos_data)
                await repo.update_status(album_id, status="COMPLETED")
        else:
            await album_repo.add_photos(album_id, photos_data)
            await album_repo.update_status(album_id, status="COMPLETED")

        # Acknowledge delivery to AI Core so it cleans up temporary S3
        try:
            await ai_client.acknowledge_results(job_uuid)
        except Exception as exc:
            logger.warning("Could not send ACK to AI Core for job %s: %s", job_uuid, exc)

        logger.info("Successfully processed and saved completed album %s in parallel", album_id)
    except Exception as exc:
        logger.exception("Failed to process completed job %s for album %s: %s", job_uuid, album_id, exc)
        if hasattr(album_repo, "session") and album_repo.session is not None:
            from app.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                repo = AlbumRepository(session=session)
                await repo.update_status(
                    album_id,
                    status="FAILED",
                    error_message=f"Failed to download results: {exc}"[:500],
                )
        else:
            await album_repo.update_status(
                album_id,
                status="FAILED",
                error_message=f"Failed to download results: {exc}"[:500],
            )



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
    storage: StorageService = Depends(get_storage_service),
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

    # Idempotency check: if album is already COMPLETED, avoid duplicate work and constraint violations
    if album.status == "COMPLETED":
        return {"status": "already_completed", "album_id": str(album.id), "success": True}

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

        # Standard AI Core contract: delegate photo downloads and S3 transfer to BackgroundTasks
        background_tasks.add_task(
            _download_and_store_results,
            album_id=album.id,
            job_uuid=job_uuid,
            album_repo=album_repo,
            storage=storage,
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
    """Support legacy callback format per AI_MODULE_WEBHOOK_CALLBACK.md."""
    raw_body = await request.body()
    _verify_webhook_auth(raw_body, x_internal_token=x_internal_token)

    try:
        data = json.loads(raw_body)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    album = await album_repo.get_by_generation_id(generation_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or invalid generation_id.",
        )

    photos_input = data.get("photos", [])
    photos_data = [
        {
            "order_index": p["order_index"],
            "object_key": p["object_key"],
            "is_cover": (p["order_index"] == 0),
            "is_favorite": False,
        }
        for p in photos_input
    ]

    await album_repo.add_photos(album.id, photos_data)
    await album_repo.update_status(album.id, status="COMPLETED")

    return {"success": True, "album_id": str(album.id)}
