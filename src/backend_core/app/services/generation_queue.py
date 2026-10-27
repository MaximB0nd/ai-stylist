"""Bounded process-local delivery queue backed by recoverable PostgreSQL state."""

import asyncio
import logging
from weakref import WeakKeyDictionary

from app.core.config import settings

logger = logging.getLogger(__name__)
_queues = WeakKeyDictionary()


class GenerationQueue:
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=settings.GENERATION_QUEUE_SIZE)
        self.images = asyncio.Semaphore(settings.GENERATION_IMAGE_CONCURRENCY)
        self.pending = set()
        self.workers = []
        self.active_workers = 0

    def start(self):
        if not self.workers:
            self.workers = [asyncio.create_task(self._worker())
                            for _ in range(settings.GENERATION_DOWNLOAD_WORKERS)]

    def submit(self, album_id, job_uuid, ai_client):
        if album_id in self.pending:
            return True
        try:
            self.queue.put_nowait((album_id, job_uuid, ai_client))
        except asyncio.QueueFull:
            return False
        self.pending.add(album_id)
        return True

    async def _worker(self):
        from app.services.generation_results import _download_and_store_results
        while True:
            album_id, job_uuid, ai_client = await self.queue.get()
            self.active_workers += 1
            try:
                # Acquire a fresh database lease only when actual processing starts.
                await _download_and_store_results(album_id, job_uuid, ai_client)
            except Exception:
                logger.exception("Queued delivery failed for album %s", album_id)
            finally:
                self.active_workers -= 1
                self.pending.discard(album_id)
                self.queue.task_done()

    async def close(self):
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        while not self.queue.empty():
            self.queue.get_nowait()
            self.queue.task_done()
        self.pending.clear()


def get_generation_queue():
    loop = asyncio.get_running_loop()
    if loop not in _queues:
        _queues[loop] = GenerationQueue()
    return _queues[loop]


async def enqueue_results(album_id, job_uuid, ai_client, token=None):
    from app.db.session import AsyncSessionLocal
    from app.db.repositories.album_repository import AlbumRepository
    if token is not None:
        async with AsyncSessionLocal() as session:
            if not await AlbumRepository(session).finish_work(
                album_id, token, status="DOWNLOADING"
            ):
                return
    delivery = get_generation_queue()
    if not delivery.submit(album_id, job_uuid, ai_client):
        logger.info("Delivery queue full; recovery will retry album %s", album_id)
