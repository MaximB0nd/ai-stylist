"""Dispatch a persisted generation, retaining identical inputs across recovery."""

from datetime import datetime, timedelta, timezone
import asyncio
import uuid

from app.core.config import settings


async def dispatch_generation(album, repo, storage, ai_client, token):
    request = album.dispatch_request
    if request is None:
        get_url = storage.presigned_internal_url
        ttl = getattr(storage, "presigned_ttl", settings.MINIO_PRESIGNED_TTL)
        request = {
            "requested_image_count": 5,
            "face_photo_url": await asyncio.to_thread(get_url, album.source_face_key),
            "body_photo_url": await asyncio.to_thread(get_url, album.source_body_key),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat(),
            "age": album.user_age,
            "height_cm": album.user_height,
            "gender": album.gender,
            "situation": album.situation,
            "styles": album.styles,
            "shoes": album.shoes,
            "impressions": album.impressions,
        }
        if not await repo.save_dispatch_request(album.id, token, request):
            return None
    # Preserve URLs and expiry exactly: AI Core fingerprints the entire request body.
    kwargs = dict(request)
    kwargs["expires_at"] = datetime.fromisoformat(kwargs["expires_at"])
    result = await ai_client.create_job(generation_id=album.generation_id, **kwargs)
    job_id = uuid.UUID(result["job_id"])
    remote_status = result.get("status", "QUEUED").upper()
    local_status = "PROCESSING" if remote_status == "PROCESSING" else "QUEUED"
    if remote_status == "FAILED":
        local_status = "FAILED"
    await repo.record_dispatch(album.id, token, job_id, local_status)
    return local_status
