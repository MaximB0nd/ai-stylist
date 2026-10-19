"""Download generated images under a renewable ownership lease."""

import asyncio
import hashlib
import logging
from typing import Optional
import uuid

import httpx

from app.db.repositories.album_repository import AlbumRepository
from app.db.session import AsyncSessionLocal
from app.services.ai_core_client import AICoreClient
from app.services.generation_lease import LeaseLostError, keep_lease
from app.core.config import settings
from app.services.retry_policy import is_retryable_delivery_error
from app.services.image_service import normalize_result

logger = logging.getLogger(__name__)


async def store_legacy_results(album_id, photos, token, repo, storage):
    """Normalize legacy object references into an isolated PNG result attempt."""
    from app.services.generation_queue import get_generation_queue
    from app.services.generation_cleanup import cleanup_attempt
    try:
        normalized = []
        for photo in photos:
            async with get_generation_queue().images:
                content = await storage.download_bytes(photo["object_key"], 15 * 1024 * 1024)
                content = await normalize_result(content)
                key = f"albums/{album_id}/{token}/look_{photo['order_index']:02d}.png"
                await storage.upload_bytes(key, content, content_type="image/png")
                normalized.append({**photo, "object_key": key})
        return await repo.complete_with_photos(album_id, normalized, token)
    except Exception as exc:
        await repo.finish_work(
            album_id, token,
            status="DOWNLOADING" if is_retryable_delivery_error(exc) else "FAILED",
            error_message="Failed to normalize callback results: " + str(exc)[:400],
        )
        return False
    finally:
        await cleanup_attempt(album_id, token, storage)

async def _download_and_store_results(
    album_id: uuid.UUID,
    job_uuid: uuid.UUID,
    ai_client: AICoreClient,
    token: Optional[uuid.UUID] = None,
) -> None:
    """Background task: fetch images from AI Core temp S3 in parallel,
    upload to permanent MinIO and persist to DB.

    Always creates its own AsyncSession because the request-scoped session
    is already closed by the time this background task runs.
    """
    # Import here to avoid circular dependency at module load time
    from app.services.storage_service import StorageService as _StorageService

    storage = _StorageService()
    if token is None:
        async with AsyncSessionLocal() as session:
            token = await AlbumRepository(session).atomic_claim_for_download(album_id)
        if token is None:
            return

    try:
        async with keep_lease(album_id, token), asyncio.timeout(settings.GENERATION_TIMEOUT_SECONDS):
            await _store_results_owned(album_id, job_uuid, ai_client, storage, token)
    except LeaseLostError:
        logger.info("Download ownership lost for album %s; stopping the old worker", album_id)
    except TimeoutError:
        # Release on the next recovery pass; the persisted generation deadline is checked there.
        logger.warning("Download deadline reached for album %s", album_id)


async def _store_results_owned(album_id, job_uuid, ai_client, storage, token):

    try:
        job_details = await ai_client.get_job(job_uuid)
        job_status = (job_details.get("status") or "").upper()
        delivery_status = (job_details.get("result_delivery_status") or "").upper()
        results = job_details.get("results") or []
        expected_count = job_details.get("requested_image_count")

        # Only AVAILABLE delivery can be downloaded and acknowledged.
        if delivery_status != "AVAILABLE":
            raise RuntimeError(
                f"AI Core job {job_uuid} has invalid delivery state {delivery_status!r}. "
                "Cannot accept or confirm expired/acknowledged delivery."
            )

        # Guard: only confirm delivery if job status is explicitly COMPLETED
        if job_status != "COMPLETED":
            raise RuntimeError(
                f"AI Core job {job_uuid} has unexpected status {job_status!r}; "
                "expected COMPLETED. Aborting to avoid confirming a bad delivery."
            )

        # Guard: AI Core may return stale/expired job with empty results.
        # We must never mark an album COMPLETED with 0 photos.
        if not results:
            raise RuntimeError(
                f"AI Core returned 0 results for job {job_uuid} (job status={job_status!r}). "
                "Cannot mark album COMPLETED with empty photo list."
            )

        # Partial success and extra results are forbidden by the AI Core contract.
        if type(expected_count) is not int or not 1 <= expected_count <= 10 or len(results) != expected_count:
            raise RuntimeError(
                f"AI Core returned {len(results)} photos, but {expected_count} were expected for job {job_uuid}. "
                "Aborting invalid delivery count."
            )

        if len(results) > 10 or any(not isinstance(item.get("order_index"), int)
                                   or not 0 <= item["order_index"] < 10 for item in results):
            raise ValueError("Invalid result count or order_index")
        if len({item["order_index"] for item in results}) != len(results):
            raise ValueError("Duplicate result order_index")

        MAX_DOWNLOAD_IMAGE_SIZE = 15 * 1024 * 1024  # 15 MiB limit per image

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            async def _download_and_upload_single(item: dict) -> dict:
                order_index = item["order_index"]
                download_url = item["download_url"]

                # Validate URL scheme to prevent arbitrary protocol injection
                from urllib.parse import urlparse
                parsed = urlparse(download_url)
                if parsed.scheme not in ("http", "https"):
                    raise ValueError(
                        f"Unsupported download URL scheme '{parsed.scheme}' at order {order_index}"
                    )

                chunks: list[bytes] = []
                total_bytes = 0

                async with http_client.stream("GET", download_url) as img_resp:
                    if img_resp.status_code != 200:
                        raise RuntimeError(
                            f"Failed to download image from AI Core at order {order_index}: HTTP {img_resp.status_code}"
                        )
                    async for chunk in img_resp.aiter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > MAX_DOWNLOAD_IMAGE_SIZE:
                            raise RuntimeError(
                                f"Image at order {order_index} exceeds maximum download limit of "
                                f"{MAX_DOWNLOAD_IMAGE_SIZE // (1024 * 1024)} MiB"
                            )
                        chunks.append(chunk)

                content = b"".join(chunks)

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
                # Separate attempts cannot overwrite files referenced by the winning worker.
                content = await normalize_result(content)
                dest_key = f"albums/{album_id}/{token}/look_{order_index:02d}.png"
                await storage.upload_bytes(dest_key, content, content_type="image/png")

                return {
                    "order_index": order_index,
                    "object_key": dest_key,
                    "is_cover": (order_index == 0),
                    "is_favorite": False,
                }

            from app.services.generation_queue import get_generation_queue
            image_slots = get_generation_queue().images

            async def _limited_image(item):
                # Hold the slot until PUT finishes, including cancellation draining.
                async with image_slots:
                    return await _download_and_upload_single(item)

            # Download and upload all images concurrently
            tasks = [asyncio.create_task(_limited_image(item)) for item in results]
            try:
                photos_data = await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            photos_data = sorted(photos_data, key=lambda p: p["order_index"])

        # Always use a fresh session — the request-scoped session is already closed
        async with AsyncSessionLocal() as session:
            from app.db.repositories.album_repository import AlbumRepository as _Repo
            repo = _Repo(session=session)
            if not await repo.complete_with_photos(album_id, list(photos_data), token):
                return

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
                # Network/storage outages remain recoverable; invalid deliveries are terminal.
                transient = is_retryable_delivery_error(exc)
                await repo.finish_work(
                    album_id, token,
                    status="DOWNLOADING" if transient else "FAILED",
                    error_message=f"Failed to download results: {exc}"[:500],
                )
        except Exception as db_exc:
            logger.exception(
                "Could not persist FAILED status for album %s after download error: %s",
                album_id,
                db_exc,
            )
    finally:
        from app.services.generation_cleanup import cleanup_attempt
        await cleanup_attempt(album_id, token, storage)
