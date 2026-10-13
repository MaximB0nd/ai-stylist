"""Regression coverage for recovery, ownership fencing, and readiness."""

from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest

from app.db.repositories.album_repository import AlbumRepository
from app.services import generation_recovery, generation_results, health_service
from app.services.generation_dispatch import dispatch_generation
from app.services import generation_lease
from app.main import app


@asynccontextmanager
async def no_heartbeat(*args):
    yield


@pytest.fixture
def recovery_state(monkeypatch):
    album = SimpleNamespace(
        id=uuid.uuid4(), generation_id=uuid.uuid4(), ai_job_id=uuid.uuid4(),
        status="QUEUED", created_at=datetime.now(timezone.utc), dispatch_request=None,
    )
    token = uuid.uuid4()
    repo = SimpleNamespace(
        claim_work=AsyncMock(return_value=token), finish_work=AsyncMock(return_value=True),
        save_dispatch_request=AsyncMock(return_value=True), record_dispatch=AsyncMock(return_value=True),
    )
    session = SimpleNamespace(get=AsyncMock(return_value=album))

    @asynccontextmanager
    async def sessions():
        yield session

    monkeypatch.setattr(generation_recovery, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(generation_recovery, "AlbumRepository", lambda session: repo)
    monkeypatch.setattr(generation_recovery, "keep_lease", no_heartbeat)
    return album, token, repo


async def test_lost_completion_webhook_is_recovered(recovery_state, monkeypatch):
    from app.services import generation_queue
    album, token, repo = recovery_state
    ai_client = SimpleNamespace(get_job=AsyncMock(return_value={"status": "COMPLETED"}))
    queue = SimpleNamespace(submit=MagicMock(return_value=True))
    monkeypatch.setattr(generation_queue, "get_generation_queue", lambda: queue)
    await generation_recovery.recover_album(album.id, ai_client, object())
    repo.finish_work.assert_awaited_once_with(album.id, token, status="DOWNLOADING")
    queue.submit.assert_called_once_with(album.id, album.ai_job_id, ai_client)


async def test_recovery_does_not_take_over_active_worker(recovery_state):
    album, token, repo = recovery_state
    repo.claim_work.return_value = None
    ai_client = SimpleNamespace(get_job=AsyncMock())
    await generation_recovery.recover_album(album.id, ai_client, object())
    ai_client.get_job.assert_not_awaited()
    repo.finish_work.assert_not_awaited()


async def test_generation_deadline_stops_infinite_polling(recovery_state):
    album, token, repo = recovery_state
    album.created_at -= timedelta(days=2)
    ai_client = SimpleNamespace(get_job=AsyncMock())
    await generation_recovery.recover_album(album.id, ai_client, object())
    ai_client.get_job.assert_not_awaited()
    assert repo.finish_work.await_args.kwargs["status"] == "FAILED"


async def test_temporary_polling_failure_remains_recoverable(recovery_state):
    album, token, repo = recovery_state
    ai_client = SimpleNamespace(get_job=AsyncMock(side_effect=httpx.ConnectError("unavailable")))
    await generation_recovery.recover_album(album.id, ai_client, object())
    assert "status" not in repo.finish_work.await_args.kwargs
    assert "Recovery failed" in repo.finish_work.await_args.kwargs["error_message"]


@pytest.mark.parametrize("local_status", ["VALIDATING", "PROCESSING", "DOWNLOADING"])
async def test_orphan_dispatch_reuses_original_urls_and_generation_id(recovery_state, local_status):
    album, token, repo = recovery_state
    album.status = local_status
    album.ai_job_id = None
    original_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    album.dispatch_request = {
        "face_photo_url": "https://minio/original-face?signature=original",
        "body_photo_url": "https://minio/original-body?signature=original",
        "expires_at": original_expiry.isoformat(), "age": 25, "height_cm": 175,
        "gender": "f", "situation": "office", "styles": ["casual"],
        "shoes": ["loafers"], "impressions": ["elegant"],
    }
    ai_client = SimpleNamespace(create_job=AsyncMock(return_value={"job_id": str(uuid.uuid4()), "status": "QUEUED"}))
    await generation_recovery.recover_album(album.id, ai_client, object())
    kwargs = ai_client.create_job.await_args.kwargs
    assert kwargs["generation_id"] == album.generation_id
    assert kwargs["face_photo_url"] == album.dispatch_request["face_photo_url"]
    assert kwargs["expires_at"] == original_expiry
    repo.save_dispatch_request.assert_not_awaited()


async def test_original_dispatch_is_persisted_before_network_send(recovery_state):
    album, token, repo = recovery_state
    album.source_face_key, album.source_body_key = "face.jpg", "body.jpg"
    album.user_age, album.user_height, album.gender = 25, 175, "f"
    album.situation, album.styles, album.shoes, album.impressions = "office", ["casual"], ["loafers"], ["elegant"]
    storage = SimpleNamespace(presigned_internal_url=lambda key: "https://minio/" + key, presigned_ttl=3600)

    async def send(**kwargs):
        repo.save_dispatch_request.assert_awaited_once()
        saved = repo.save_dispatch_request.await_args.args[2]
        assert kwargs["face_photo_url"] == saved["face_photo_url"]
        return {"job_id": str(uuid.uuid4()), "status": "QUEUED"}

    await dispatch_generation(album, repo, storage, SimpleNamespace(create_job=send), token)


async def test_completion_commits_photos_and_status_once():
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid.uuid4()
    session = MagicMock(execute=AsyncMock(return_value=result), commit=AsyncMock(), rollback=AsyncMock())
    completed = await AlbumRepository(session).complete_with_photos(
        uuid.uuid4(), [{"order_index": 0, "object_key": "albums/test/look.webp"}], uuid.uuid4()
    )
    assert completed
    assert session.execute.await_count == 2
    session.add_all.assert_called_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


async def test_photo_insert_failure_rolls_back_completion():
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid.uuid4()
    session = MagicMock(execute=AsyncMock(return_value=result), commit=AsyncMock(side_effect=RuntimeError("insert failed")), rollback=AsyncMock())
    with pytest.raises(RuntimeError, match="insert failed"):
        await AlbumRepository(session).complete_with_photos(
            uuid.uuid4(), [{"order_index": 0, "object_key": "albums/test/look.webp"}], uuid.uuid4()
        )
    session.rollback.assert_awaited_once()


async def test_stale_owner_cannot_replace_photos():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock(execute=AsyncMock(return_value=result), commit=AsyncMock(), rollback=AsyncMock())
    assert not await AlbumRepository(session).complete_with_photos(uuid.uuid4(), [], uuid.uuid4())
    session.execute.assert_awaited_once()
    session.add_all.assert_not_called()
    session.commit.assert_not_awaited()


async def test_heartbeat_renews_and_stops_worker_on_lost_lease(monkeypatch):
    repo = SimpleNamespace(renew_lease=AsyncMock(side_effect=[True, False]))

    @asynccontextmanager
    async def sessions():
        yield object()

    monkeypatch.setattr(generation_lease, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(generation_lease, "AlbumRepository", lambda session: repo)
    monkeypatch.setattr(generation_lease.settings, "GENERATION_LEASE_SECONDS", 0.03)

    with pytest.raises(generation_lease.LeaseLostError):
        async with generation_lease.keep_lease(uuid.uuid4(), uuid.uuid4()):
            await asyncio.sleep(1)

    assert repo.renew_lease.await_count == 2


async def test_download_network_failure_is_retried_without_ack(monkeypatch):
    repo = SimpleNamespace(finish_work=AsyncMock())

    @asynccontextmanager
    async def sessions():
        yield object()

    monkeypatch.setattr(generation_results, "AsyncSessionLocal", sessions)
    monkeypatch.setattr("app.db.repositories.album_repository.AlbumRepository", lambda session: repo)
    ai_client = SimpleNamespace(
        get_job=AsyncMock(side_effect=httpx.ConnectError("temporary outage")),
        acknowledge_results=AsyncMock(),
    )
    album_id, token = uuid.uuid4(), uuid.uuid4()
    await generation_results._store_results_owned(album_id, uuid.uuid4(), ai_client, object(), token)
    assert repo.finish_work.await_args.args == (album_id, token)
    assert repo.finish_work.await_args.kwargs["status"] == "DOWNLOADING"
    ai_client.acknowledge_results.assert_not_awaited()


@pytest.mark.parametrize("failed", [None, "postgresql", "minio"])
async def test_health_reports_dependency_failures(monkeypatch, failed):
    async def postgres():
        if failed == "postgresql":
            raise ConnectionError("private connection details")

    def minio():
        if failed == "minio":
            raise ConnectionError("private access key")

    monkeypatch.setattr(health_service, "check_postgres", postgres)
    monkeypatch.setattr(health_service, "check_minio", minio)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == (503 if failed else 200)
    assert response.json()["checks"] == {
        "postgresql": "unavailable" if failed == "postgresql" else "ok",
        "minio": "unavailable" if failed == "minio" else "ok",
    }
    assert "private" not in response.text


async def test_pending_callback_is_recovered_without_remote_job(recovery_state):
    album, token, repo = recovery_state
    album.ai_job_id = None
    album.pending_callback = [{"order_index": 0, "object_key": "albums/test.webp"}]
    repo.complete_with_photos = AsyncMock(return_value=True)
    client = SimpleNamespace(get_job=AsyncMock(), create_job=AsyncMock())
    await generation_recovery.recover_album(album.id, client, object())
    repo.complete_with_photos.assert_awaited_once_with(album.id, album.pending_callback, token)
    client.get_job.assert_not_awaited()


async def test_busy_callback_is_persisted_before_acknowledgement():
    from app.api.v1.endpoints.internal import _accept_callback, LegacyCallbackPayload
    album = SimpleNamespace(id=uuid.uuid4())
    repo = SimpleNamespace(persist_callback=AsyncMock(return_value="accepted"),
                           atomic_claim_for_download=AsyncMock(return_value=None), complete_with_photos=AsyncMock())
    result = await _accept_callback(repo, album, LegacyCallbackPayload(photos=[{"order_index": 0, "object_key": "albums/test.webp"}]))
    assert result["status"] == "accepted"
    repo.persist_callback.assert_awaited_once()
    repo.complete_with_photos.assert_not_awaited()


@pytest.mark.parametrize("referenced", [True, False])
async def test_orphan_cleanup_preserves_only_referenced_files(referenced):
    locked, reference = MagicMock(), MagicMock()
    locked.scalar_one_or_none.return_value = SimpleNamespace(processing_token=None, pending_callback=None)
    reference.scalar_one_or_none.return_value = uuid.uuid4() if referenced else None
    session = SimpleNamespace(execute=AsyncMock(side_effect=[locked, reference]), rollback=AsyncMock())
    storage = SimpleNamespace(delete_attempt=MagicMock())
    await AlbumRepository(session).delete_orphan_attempt(uuid.uuid4(), uuid.uuid4(), "albums/test/", storage)
    assert storage.delete_attempt.call_count == (0 if referenced else 1)


async def test_cancelled_upload_waits_for_synchronous_put(monkeypatch):
    import threading
    from app.services.storage_service import StorageService
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    storage = StorageService.__new__(StorageService)
    def put(*args):
        started.set()
        release.wait(timeout=5)
        finished.set()
    monkeypatch.setattr(storage, "_put_object", put)
    task = asyncio.create_task(storage.upload_bytes("key", b"content"))
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


def test_public_signing_uses_internal_region_without_public_network(monkeypatch):
    from app.services.storage_service import StorageService
    storage = StorageService()
    monkeypatch.setattr(storage.client, "_get_region", lambda bucket: "eu-west-1")
    def no_network(*args, **kwargs):
        raise AssertionError("Signing must not contact the public endpoint")
    monkeypatch.setattr("minio.api.Minio._url_open", no_network)
    assert "eu-west-1" in storage.presigned_public_url("albums/test.webp")
