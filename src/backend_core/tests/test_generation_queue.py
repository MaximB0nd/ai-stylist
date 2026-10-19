from tests.image_fixtures import image_bytes
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid
import pytest

from app.services import generation_queue, generation_results


async def test_queue_bounds_workers_backlog_and_deduplicates(monkeypatch):
    monkeypatch.setattr(generation_queue.settings, "GENERATION_QUEUE_SIZE", 2)
    monkeypatch.setattr(generation_queue.settings, "GENERATION_DOWNLOAD_WORKERS", 1)
    entered, release = asyncio.Event(), asyncio.Event()
    processed = []

    async def download(album_id, *args):
        processed.append(album_id)
        entered.set()
        await release.wait()

    monkeypatch.setattr(generation_results, "_download_and_store_results", download)
    queue = generation_queue.GenerationQueue()
    ids = [uuid.uuid4() for _ in range(4)]
    queue.start()
    try:
        assert queue.submit(ids[0], uuid.uuid4(), object())
        await entered.wait()
        assert queue.submit(ids[0], uuid.uuid4(), object())
        assert queue.submit(ids[1], uuid.uuid4(), object())
        assert queue.submit(ids[2], uuid.uuid4(), object())
        assert not queue.submit(ids[3], uuid.uuid4(), object())
        assert processed == [ids[0]]
        release.set()
        await asyncio.wait_for(queue.queue.join(), 2)
        assert processed == ids[:3]
        assert not queue.pending
    finally:
        await queue.close()


async def test_worker_failure_does_not_stop_queue(monkeypatch):
    monkeypatch.setattr(generation_queue.settings, "GENERATION_DOWNLOAD_WORKERS", 1)
    download = AsyncMock(side_effect=[RuntimeError("temporary failure"), None])
    monkeypatch.setattr(generation_results, "_download_and_store_results", download)
    queue = generation_queue.GenerationQueue()
    for _ in range(2):
        queue.submit(uuid.uuid4(), uuid.uuid4(), object())
    queue.start()
    try:
        await asyncio.wait_for(queue.queue.join(), 2)
        assert download.await_count == 2
        assert not queue.pending
    finally:
        await queue.close()


@pytest.mark.parametrize("count", [5, 10])
async def test_image_limit_is_shared_between_albums_and_covers_upload(monkeypatch, count):
    queue = generation_queue.GenerationQueue()
    queue.images = asyncio.Semaphore(2)
    monkeypatch.setattr(generation_queue, "get_generation_queue", lambda: queue)
    release, full = asyncio.Event(), asyncio.Event()
    active = peak = uploaded = 0

    class Response:
        status_code = 200

        async def aiter_bytes(self):
            yield image_bytes()

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @asynccontextmanager
        async def stream(self, *args):
            yield Response()

    async def upload(*args, **kwargs):
        nonlocal active, peak, uploaded
        active += 1
        peak = max(peak, active)
        if active == 2:
            full.set()
        try:
            await release.wait()
            uploaded += 1
        finally:
            active -= 1

    @asynccontextmanager
    async def sessions():
        yield object()

    repo = SimpleNamespace(complete_with_photos=AsyncMock(return_value=True), finish_work=AsyncMock())
    monkeypatch.setattr(generation_results.httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr(generation_results, "AsyncSessionLocal", sessions)
    monkeypatch.setattr("app.db.repositories.album_repository.AlbumRepository", lambda **kwargs: repo)
    monkeypatch.setattr("app.services.generation_cleanup.cleanup_attempt", AsyncMock())
    ai = SimpleNamespace(get_job=AsyncMock(return_value={
        "status": "COMPLETED", "result_delivery_status": "AVAILABLE", "requested_image_count": count,
        "results": [{"order_index": i, "download_url": "http://storage/image"} for i in range(count)],
    }), acknowledge_results=AsyncMock())
    storage = SimpleNamespace(upload_bytes=upload)
    tasks = [asyncio.create_task(generation_results._store_results_owned(
        uuid.uuid4(), uuid.uuid4(), ai, storage, uuid.uuid4())) for _ in range(2)]
    try:
        await asyncio.wait_for(full.wait(), 2)
        await asyncio.sleep(0)
        assert active == peak == 2
        release.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 2)
        assert uploaded == count * 2
        assert peak == 2
        assert repo.complete_with_photos.await_count == 2
    finally:
        release.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
