"""Conservative garbage collection of isolated, unreferenced result attempts."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import uuid

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.repositories.album_repository import AlbumRepository
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

async def cleanup_attempt(album_id, token, storage):
    try:
        async with AsyncSessionLocal() as session:
            await AlbumRepository(session).delete_orphan_attempt(
                album_id, token, f"albums/{album_id}/{token}/", storage)
    except Exception:
        # Fail closed: never remove files when PostgreSQL cannot prove them unreferenced.
        logger.exception("Could not clean result attempt %s/%s", album_id, token)

async def cleanup_orphan_attempts(storage=None):
    storage = storage or StorageService()
    objects = await asyncio.to_thread(storage.list_attempt_objects)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(3600, settings.GENERATION_LEASE_SECONDS * 2))
    attempts = {}
    for obj in objects:
        parts = obj.object_name.split("/")
        if len(parts) != 4 or obj.last_modified is None:
            continue
        try:
            album_id, token = uuid.UUID(parts[1]), uuid.UUID(parts[2])
        except ValueError:
            continue
        key = (album_id, token)
        attempts[key] = max(attempts.get(key, obj.last_modified), obj.last_modified)
    for (album_id, token), modified in attempts.items():
        if modified < cutoff:
            await cleanup_attempt(album_id, token, storage)
