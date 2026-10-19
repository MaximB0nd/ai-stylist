"""LAN URL signing and restart-safe delivery acknowledgement checks."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import uuid

import httpx
import pytest
from minio import Minio

from app.services import generation_ack
from app.services.ai_core_client import AICoreClient, AICoreError
from app.services.retry_policy import retry_deadline
from app.services.storage_service import StorageService


def test_ai_url_uses_lan_host_and_internal_bucket_region():
    storage = StorageService.__new__(StorageService)
    storage.client = Mock()
    storage.client._get_region.return_value = "eu-west-1"
    storage.ai_endpoint = "192.168.1.10:9000"
    storage.bucket, storage.presigned_ttl = "stylist", 3600
    storage.public_client = Minio("localhost:9000", secure=False, region="eu-west-1")
    url = storage.presigned_internal_url("sources/user/face.png")
    assert url.startswith("http://192.168.1.10:9000/stylist/sources/user/face.png?")
    assert "%2Feu-west-1%2Fs3%2Faws4_request" in url
    storage.client._get_region.assert_called_once_with("stylist")
    storage.client.presigned_get_object.assert_not_called()
    assert storage.presigned_public_url("sources/user/face.png").startswith("http://localhost:9000/")


@pytest.mark.parametrize("header, expected", [("120", 120), ("0", 0), ("-1", None), ("nonsense", None)])
async def test_http_retry_after_is_preserved(header, expected):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
        503, headers={"Retry-After": header}, json={"error": {"code": "BUSY"}},
    ))) as http:
        client = AICoreClient(base_url="http://ai", client=http)
        with pytest.raises(AICoreError) as result:
            await client.get_job(uuid.uuid4())
        assert result.value.retry_after_seconds == expected
        if expected:
            assert retry_deadline(result.value) >= datetime.now(timezone.utc) + timedelta(seconds=expected - 1)


@pytest.fixture
def ack_repo(monkeypatch):
    repo = SimpleNamespace(record_result_ack=AsyncMock(), get_pending_result_acks=AsyncMock())
    @asynccontextmanager
    async def sessions():
        yield object()
    monkeypatch.setattr(generation_ack, "AsyncSessionLocal", sessions)
    monkeypatch.setattr("app.db.repositories.album_repository.AlbumRepository", lambda **kwargs: repo)
    return repo


async def test_ack_failed_response_then_recovery_success(ack_repo):
    album_id, job_id = uuid.uuid4(), uuid.uuid4()
    ai = SimpleNamespace(acknowledge_results=AsyncMock(side_effect=AICoreError("offline")))
    await generation_ack.acknowledge_saved_results(album_id, job_id, ai)
    failure = ack_repo.record_result_ack.await_args.kwargs
    assert failure["pending"] and failure["next_attempt_at"] > datetime.now(timezone.utc)
    # Simulate a fresh pass reading the durable pending row after process restart.
    ack_repo.get_pending_result_acks.return_value = [(album_id, job_id)]
    ai.acknowledge_results.side_effect = None
    assert await generation_ack.recover_result_acks(ai) == 1
    assert ai.acknowledge_results.await_count == 2
    assert ack_repo.record_result_ack.await_args.kwargs == {
        "pending": False, "next_attempt_at": None, "error": None,
    }


async def test_expired_ack_does_not_fail_saved_album(ack_repo):
    ai = SimpleNamespace(acknowledge_results=AsyncMock(side_effect=AICoreError(
        "expired", 409, {"error": {"code": "RESULTS_EXPIRED"}},
    )))
    await generation_ack.acknowledge_saved_results(uuid.uuid4(), uuid.uuid4(), ai)
    assert ack_repo.record_result_ack.await_args.kwargs == {
        "pending": False, "next_attempt_at": None, "error": "RESULTS_EXPIRED before ACK",
    }


async def test_ack_retry_after_and_failed_db_write_leave_pending(ack_repo):
    error = AICoreError("busy", 429)
    error.retry_after_seconds = 120
    ai = SimpleNamespace(acknowledge_results=AsyncMock(side_effect=error))
    ack_repo.record_result_ack.side_effect = OSError("database offline")
    await generation_ack.acknowledge_saved_results(uuid.uuid4(), uuid.uuid4(), ai)
    args = ack_repo.record_result_ack.await_args.kwargs
    assert args["pending"] and args["next_attempt_at"] > datetime.now(timezone.utc) + timedelta(seconds=119)
