"""Durable, idempotent acknowledgements after local delivery has committed."""
import asyncio
import json
import logging

from app.db.session import AsyncSessionLocal
from app.services.ai_core_client import AICoreClient, AICoreError
from app.services.retry_policy import retry_deadline

logger = logging.getLogger(__name__)


async def acknowledge_saved_results(album_id, job_id, ai_client, *, session_factory=None):
    # A lost response is safe: the public contract allows repeated ACK requests.
    pending, deadline, error = False, None, None
    try:
        await ai_client.acknowledge_results(job_id)
    except Exception as exc:
        pending = True
        deadline = retry_deadline(exc)
        error = f"ACK pending ({type(exc).__name__})"
        if isinstance(exc, AICoreError):
            error = f"ACK HTTP {exc.status_code}"
            try:
                body = json.loads(exc.response_body) if isinstance(exc.response_body, str) else exc.response_body
                code = (body or {}).get("error", {}).get("code")
            except (ValueError, AttributeError, TypeError):
                code = None
            if exc.status_code == 409 and code == "RESULTS_EXPIRED":
                # The permanent copies remain usable; remote temporary files have expired.
                pending, deadline, error = False, None, "RESULTS_EXPIRED before ACK"
        logger.warning("Delivery ACK deferred for album %s: %s", album_id, error)
    try:
        from app.db.repositories.album_repository import AlbumRepository
        async with (session_factory or AsyncSessionLocal)() as session:
            await AlbumRepository(session=session).record_result_ack(
                album_id, job_id, pending=pending, next_attempt_at=deadline, error=error,
            )
    except Exception:
        # The previously committed pending flag survives failed writes and process exit.
        logger.exception("Could not persist ACK outcome for album %s", album_id)


async def recover_result_acks(ai_client=None):
    from app.db.repositories.album_repository import AlbumRepository
    async with AsyncSessionLocal() as session:
        jobs = await AlbumRepository(session=session).get_pending_result_acks()
    semaphore = asyncio.Semaphore(4)
    client = ai_client or AICoreClient()

    async def send(album_id, job_id):
        async with semaphore:
            await acknowledge_saved_results(album_id, job_id, client)

    outcomes = await asyncio.gather(*(send(*row) for row in jobs), return_exceptions=True)
    for outcome in outcomes:
        if isinstance(outcome, Exception):
            logger.error("ACK recovery worker failed: %s", outcome)
    return len(jobs)
