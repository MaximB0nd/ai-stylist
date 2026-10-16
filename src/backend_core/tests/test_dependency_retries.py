"""Exercise recoverable dispatches and actual MinIO SDK exception types."""
from contextlib import asynccontextmanager
import hashlib
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

from fastapi import UploadFile
import httpx
from minio.error import InvalidResponseError, S3Error, ServerError
from PIL import Image
import pytest
from urllib3.exceptions import MaxRetryError, NewConnectionError, ReadTimeoutError
from urllib3.response import HTTPResponse

from app.schemas.generation import GenerationRequestForm
from app.services.ai_core_client import AICoreClient
from app.services.generation_service import GenerationService
from app.services import generation_results
from tests.test_generations import InMemoryAlbumRepository, InMemoryStorageService, FAKE_USER_ID


def s3_error(code, status):
    return S3Error(HTTPResponse(status=status), code, "test error", "resource", "request", "host")


def png_result(order_index=0):
    output = BytesIO()
    Image.new("RGB", (1024, 1536), (32, 64, 96)).save(output, format="PNG")
    content = output.getvalue()
    return content, {
        "order_index": order_index, "download_url": "http://temporary/image",
        "checksum_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content), "format": "png", "width": 1024, "height": 1536,
        "model_version": "model-1", "prompt_version": "prompt-1",
        "outfit_spec_version": "1.0", "seed": 42,
    }


@pytest.mark.parametrize("error, expected", [
    (MaxRetryError(None, "/object", NewConnectionError(None, "connection refused")), "DOWNLOADING"),
    (ReadTimeoutError(None, "/object", "timeout"), "DOWNLOADING"),
    (ServerError("unavailable", 503), "DOWNLOADING"),
    (InvalidResponseError(502, "text/html", "bad gateway"), "DOWNLOADING"),
    (s3_error("SlowDown", 503), "DOWNLOADING"),
    (s3_error("AccessDenied", 403), "FAILED"),
    (s3_error("NoSuchBucket", 404), "FAILED"),
])
async def test_minio_upload_outage_is_recoverable_without_ack(monkeypatch, error, expected):
    content, item = png_result()
    repo = SimpleNamespace(finish_work=AsyncMock(), complete_with_photos=AsyncMock())
    @asynccontextmanager
    async def sessions():
        yield object()
    class Response:
        status_code = 200
        async def aiter_bytes(self):
            yield content
    class Http:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        @asynccontextmanager
        async def stream(self, *args):
            yield Response()
    monkeypatch.setattr(generation_results, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(generation_results.httpx, "AsyncClient", lambda **kwargs: Http())
    monkeypatch.setattr("app.db.repositories.album_repository.AlbumRepository", lambda **kwargs: repo)
    monkeypatch.setattr("app.services.generation_cleanup.cleanup_attempt", AsyncMock())
    ai = SimpleNamespace(get_job=AsyncMock(return_value={
        "status": "COMPLETED", "result_delivery_status": "AVAILABLE", "requested_image_count": 1,
        "results": [item],
    }), acknowledge_results=AsyncMock())
    storage = SimpleNamespace(upload_bytes=AsyncMock(side_effect=error))
    await generation_results._store_results_owned(uuid.uuid4(), uuid.uuid4(), ai, storage, uuid.uuid4())
    storage.upload_bytes.assert_awaited_once()
    assert repo.finish_work.await_args.kwargs["status"] == expected
    repo.complete_with_photos.assert_not_awaited()
    ai.acknowledge_results.assert_not_awaited()


@pytest.mark.parametrize("failure", [429, 503, 500, "timeout"])
async def test_initial_dispatch_outage_returns_accepted_and_replays_same_job(failure):
    requests = []
    remote_id = uuid.uuid4()
    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("response lost", request=request)
            return httpx.Response(failure, json={"error": {"code": "SERVICE_UNAVAILABLE", "retryable": True}})
        return httpx.Response(200, json={"job_id": str(remote_id), "status": "QUEUED"})
    repo = InMemoryAlbumRepository()
    storage = InMemoryStorageService()
    form = GenerationRequestForm(age=25, height=175, gender="m", situation="office",
                                 styles="casual", shoes="loafers", impressions="confident")
    def photo():
        return UploadFile(filename="photo.jpg", file=BytesIO(b"\xff\xd8\xff\xe0test"), headers={"content-type": "image/jpeg"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        ai = AICoreClient(client=http)
        result = await GenerationService(repo, storage, ai).create_generation(FAKE_USER_ID, photo(), photo(), form)
        album = next(iter(repo.albums.values()))
        assert result.generation_id == album.generation_id
        assert result.status == album.status == "VALIDATING"
        assert album.processing_token is None
        assert album.dispatch_request is not None
        # Exercise the same persisted replay function used by recovery.
        from app.services.generation_dispatch import dispatch_generation
        token = await repo.claim_work(album.id, ["VALIDATING"])
        await dispatch_generation(album, repo, storage, ai, token)
    assert len(repo.albums) == 1
    assert album.ai_job_id == remote_id
    assert album.status == "QUEUED"
    assert requests[0].content == requests[1].content
    assert requests[0].headers["Idempotency-Key"] == requests[1].headers["Idempotency-Key"]
