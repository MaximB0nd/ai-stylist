"""Regression tests for the current public AI Core wire contract."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import httpx
import pytest

from app.services.ai_core_client import AICoreClient, AICoreError
from app.services import generation_results


def inputs():
    return dict(generation_id=uuid.uuid4(), face_photo_url="http://minio:9000/face",
                body_photo_url="http://minio:9000/body",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                age=25, height_cm=175, gender="f", situation="street",
                styles=["casual"], shoes=["sneakers"], impressions=["relaxed"])


async def test_replayed_request_keeps_identical_body_and_idempotency_key():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(201 if len(requests) == 1 else 200,
                              json={"job_id": str(uuid.uuid4()), "status": "QUEUED"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AICoreClient(base_url="http://ai-core", client=http)
        kwargs = inputs()
        await client.create_job(**kwargs)
        await client.create_job(**kwargs)
    assert requests[0].content == requests[1].content
    assert requests[0].headers["Idempotency-Key"] == requests[1].headers["Idempotency-Key"]
    assert "authorization" not in requests[0].headers


@pytest.mark.parametrize("override", [
    {"styles": ["sport"]}, {"styles": ["streetwear"]}, {"styles": ["casual", "classic"]},
    {"shoes": []}, {"impressions": ["casual"]}, {"situation": "casual"},
    {"gender": "unspecified"}, {"requested_image_count": 0}, {"requested_image_count": 11},
    {"requested_image_count": True}, {"face_photo_url": "https://minio/face"},
    {"face_photo_url": "http://user:secret@minio/face"}, {"face_photo_url": "http://minio/face#fragment"},
])
async def test_unsupported_inputs_never_reach_ai_core(override):
    def handler(request):
        pytest.fail("Invalid input must be rejected before the HTTP request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(AICoreError):
            await AICoreClient(client=http).create_job(**(inputs() | override))


@pytest.mark.parametrize("status", [429, 503])
async def test_ai_core_unavailable_and_overloaded_responses(status):
    def handler(request):
        return httpx.Response(status, headers={"Retry-After": "30"},
                              json={"error": {"code": "SERVICE_UNAVAILABLE", "message": "Try later", "retryable": True}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(AICoreError) as error:
            await AICoreClient(client=http).create_job(**inputs())
        assert error.value.status_code == status


@pytest.mark.parametrize("details", [
    {"result_delivery_status": "EXPIRED"},
    {"result_delivery_status": "ACKNOWLEDGED"},
    {"result_delivery_status": None, "delivery_status": "AVAILABLE"},
    {"requested_image_count": 5},
    {"requested_image_count": True},
    {"results": [{"order_index": i, "download_url": "http://temporary/image"} for i in range(2)]},
])
async def test_invalid_deliveries_are_not_saved_or_acknowledged(monkeypatch, details):
    repo = SimpleNamespace(finish_work=AsyncMock(), complete_with_photos=AsyncMock())
    @asynccontextmanager
    async def sessions():
        yield object()
    monkeypatch.setattr(generation_results, "AsyncSessionLocal", sessions)
    monkeypatch.setattr("app.db.repositories.album_repository.AlbumRepository", lambda **kwargs: repo)
    monkeypatch.setattr("app.services.generation_cleanup.cleanup_attempt", AsyncMock())
    job = {"status": "COMPLETED", "result_delivery_status": "AVAILABLE", "requested_image_count": 1,
           "results": [{"order_index": 0, "download_url": "http://temporary/image"}]} | details
    ai = SimpleNamespace(get_job=AsyncMock(return_value=job), acknowledge_results=AsyncMock())
    storage = SimpleNamespace(upload_bytes=AsyncMock())
    await generation_results._store_results_owned(uuid.uuid4(), uuid.uuid4(), ai, storage, uuid.uuid4())
    repo.complete_with_photos.assert_not_awaited()
    storage.upload_bytes.assert_not_awaited()
    ai.acknowledge_results.assert_not_awaited()
    assert repo.finish_work.await_args.kwargs["status"] == "FAILED"
