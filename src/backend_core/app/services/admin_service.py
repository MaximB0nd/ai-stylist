"""Administrative read orchestration, separated from HTTP rendering."""
import asyncio
import re
from datetime import datetime, timezone
from app.db.session import AsyncSessionLocal
from app.db.repositories.admin_repository import AdminRepository
from app.db.repositories.album_repository import AlbumRepository


def safe_error(value):
    return re.sub(r"https?://[^\s]+", "[URL hidden]", str(value or ""))[:512]


async def overview():
    async with AsyncSessionLocal() as session:
        return await AdminRepository(session).overview()


async def task(album_id):
    async with AsyncSessionLocal() as session:
        album = await AlbumRepository(session).get_by_id_with_photos(album_id)
        if album is None: return None
        data = {name: getattr(album, name) for name in (
            "id", "generation_id", "ai_job_id", "user_id", "status", "created_at", "updated_at", "finished_at",
            "situation", "styles", "shoes", "impressions", "next_retry_at", "results_ack_pending",
            "results_ack_next_attempt_at", "results_ack_error")}
        data["error_message"] = safe_error(album.error_message)
        data["results_ack_error"] = safe_error(data["results_ack_error"])
        data["requested_image_count"] = (album.dispatch_request or {}).get("requested_image_count")
        data["duration"] = duration(album)
        data["saved_photos"] = len(album.photos)
        keys = [photo.object_key for photo in album.photos]
    from app.services.storage_service import StorageService
    storage = StorageService()
    semaphore = asyncio.Semaphore(4)
    async def sign(key):
        async with semaphore:
            return await asyncio.to_thread(storage.presigned_public_url, key)
    try:
        data["photos"] = await asyncio.wait_for(asyncio.gather(*(sign(key) for key in keys)), timeout=5)
    except Exception:
        data["photos"] = []
        data["photo_access"] = "MinIO temporarily unavailable; refresh the page"
    return data


def duration(album):
    if album.finished_at is None and album.status in ("COMPLETED", "FAILED"): return "неизвестно (старая задача)"
    return str(max(0, int(((album.finished_at or datetime.now(timezone.utc)) - album.created_at).total_seconds()))) + " сек."


async def generations(status=None, search=None, offset=0, since=None, until=None):
    async with AsyncSessionLocal() as session:
        return await AdminRepository(session).generations(status, search, offset, since, until)


async def user_details(user_id):
    async with AsyncSessionLocal() as session:
        return await AdminRepository(session).user_details(user_id)
