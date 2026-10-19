"""Periodically reconcile persisted generations with AI Core."""

import asyncio
from datetime import datetime, timezone
import logging

from app.core.config import settings
from app.db.repositories.album_repository import AlbumRepository
from app.db.session import AsyncSessionLocal
from app.models.album import Album
from app.services.ai_core_client import AICoreClient, AICoreError
from app.services.generation_dispatch import dispatch_generation
from app.services.generation_lease import keep_lease
from app.services.storage_service import StorageService
from app.services.retry_policy import retry_deadline

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = ["VALIDATING", "QUEUED", "PROCESSING", "DOWNLOADING"]


async def recover_album(album_id, ai_client, storage):
    async with AsyncSessionLocal() as session:
        repo = AlbumRepository(session)
        token = await repo.claim_work(album_id, ACTIVE_STATUSES)
        if token is None:
            return
        album = await session.get(Album, album_id)
        try:
            async with keep_lease(album_id, token), asyncio.timeout(settings.GENERATION_TIMEOUT_SECONDS):
                pending = getattr(album, "pending_callback", None)
                if pending:
                    if await repo.finish_work(album_id, token, release=False, status="DOWNLOADING"):
                        from app.services.generation_results import store_legacy_results
                        await store_legacy_results(album_id, pending, token, repo, storage)
                    return
                age = (datetime.now(timezone.utc) - album.created_at).total_seconds()
                if age >= settings.GENERATION_TIMEOUT_SECONDS:
                    await repo.finish_work(album_id, token, status="FAILED", error_message="Generation deadline exceeded")
                    return
                if not album.ai_job_id and (album.status == "VALIDATING" or album.dispatch_request):
                    await dispatch_generation(album, repo, storage, ai_client, token)
                    return
                if not album.ai_job_id:
                    await repo.finish_work(album_id, token, status="FAILED", error_message="Missing AI job ID; cannot recover generation")
                    return
                details = await ai_client.get_job(album.ai_job_id)
                remote_status = details.get("status", "").upper()
                if remote_status == "COMPLETED":
                    if not await repo.finish_work(album_id, token, status="DOWNLOADING"):
                        return
                    from app.services.generation_queue import get_generation_queue
                    get_generation_queue().submit(album_id, album.ai_job_id, ai_client)
                elif remote_status in ("FAILED", "CANCELLED", "EXPIRED"):
                    await repo.finish_work(album_id, token, status="FAILED", error_message=str(details.get("error") or remote_status)[:500])
                elif remote_status == "PROCESSING":
                    # Do not regress a download on an inconsistent remote response.
                    status = "DOWNLOADING" if album.status == "DOWNLOADING" else "PROCESSING"
                    await repo.finish_work(album_id, token, status=status)
                else:
                    await repo.finish_work(album_id, token)
        except Exception as exc:
            logger.warning("Recovery failed for album %s: %s", album_id, exc)
            # The session may be invalid after a DB error; release through a fresh one.
            async with AsyncSessionLocal() as error_session:
                terminal = isinstance(exc, AICoreError) and exc.status_code in (400, 404, 409, 410, 422)
                values = {"error_message": "Recovery failed: " + str(exc)[:470]}
                if terminal:
                    values["status"] = "FAILED"
                else:
                    values["next_retry_at"] = retry_deadline(exc)
                await AlbumRepository(error_session).finish_work(album_id, token, **values)


async def recovery_pass(ai_client=None, storage=None):
    ai_client = ai_client or AICoreClient()
    storage = storage or StorageService()
    async with AsyncSessionLocal() as session:
        albums = await AlbumRepository(session).get_recoverable_albums()
        album_ids = [album.id for album in albums]
    semaphore = asyncio.Semaphore(4)

    async def recover_one(album_id):
        async with semaphore:
            await recover_album(album_id, ai_client, storage)

    outcomes = await asyncio.gather(*(recover_one(album_id) for album_id in album_ids), return_exceptions=True)
    for outcome in outcomes:
        if isinstance(outcome, Exception):
            logger.error("Generation recovery worker failed: %s", outcome)
    return len(album_ids)


async def recovery_loop():
    while True:
        try:
            await recovery_pass()
            from app.services.generation_cleanup import cleanup_orphan_attempts
            await cleanup_orphan_attempts()
        except Exception:
            logger.exception("Generation reconciliation failed; retrying on the next pass")
        try:
            from app.services.generation_ack import recover_result_acks
            await recover_result_acks()
        except Exception:
            logger.exception("ACK reconciliation failed; retrying on the next pass")
        await asyncio.sleep(settings.GENERATION_RECOVERY_INTERVAL_SECONDS)
