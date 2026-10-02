"""Tests for AICoreClient and its integration with GenerationService."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

import httpx
import pytest

backend_core_dir = Path(__file__).resolve().parent.parent
if str(backend_core_dir) not in sys.path:
    sys.path.insert(0, str(backend_core_dir))

from app.services.ai_core_client import AICoreClient, AICoreError
from app.services.generation_service import GenerationService


@pytest.mark.asyncio
async def test_ai_core_create_job_success():
    """Verify payload mapping and headers when creating a job."""
    recorded_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_request["url"] = str(request.url)
        recorded_request["headers"] = dict(request.headers)
        recorded_request["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
                "status": "QUEUED",
                "requested_image_count": 10,
                "status_url": "/v1/jobs/c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = AICoreClient(
            base_url="http://fake-ai-core",
            service_token="secret-token",
            client=http_client,
        )

        gen_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        result = await client.create_job(
            generation_id=gen_id,
            face_photo_url="https://minio/face.jpg",
            body_photo_url="https://minio/body.jpg",
            expires_at=now,
            age=25,
            height_cm=175,
            gender="m",
            situation="office",
            styles=["minimalism"],
            shoes=["loafers"],
            impressions=["confident"],
        )
        assert result["job_id"] == "c84dfb50-f331-4c12-88f5-3c1a3e6015aa"
        assert result["status"] == "QUEUED"

        # Check recorded request
        assert recorded_request["url"] == "http://fake-ai-core/v1/jobs"
        assert recorded_request["headers"]["authorization"] == "Bearer secret-token"
        assert recorded_request["headers"]["idempotency-key"] == str(gen_id)

        body = recorded_request["body"]
        assert body["person"]["gender"] == "male"
        assert body["person"]["age"] == 25
        assert body["preferences"]["occasion"] == "office"
        assert body["inputs"]["face_photo_url"] == "https://minio/face.jpg"


@pytest.mark.asyncio
async def test_ai_core_create_job_error_raises_exception():
    """Verify AICoreError is raised on 4xx/5xx responses."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "INVALID_REQUEST", "message": "Bad input"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = AICoreClient(
            base_url="http://fake-ai-core",
            service_token="secret-token",
            client=http_client,
        )

        with pytest.raises(AICoreError) as exc_info:
            await client.create_job(
                generation_id=uuid.uuid4(),
                face_photo_url="https://minio/face.jpg",
                body_photo_url="https://minio/body.jpg",
                expires_at=datetime.now(timezone.utc),
                age=25,
                height_cm=175,
                gender="f",
                situation="street",
                styles=["casual"],
                shoes=["sneakers"],
                impressions=["relaxed"],
            )
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_ai_core_get_job():
    """Verify get_job correctly fetches state."""
    job_id = "c84dfb50-f331-4c12-88f5-3c1a3e6015aa"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"http://fake-ai-core/v1/jobs/{job_id}"
        return httpx.Response(200, json={"job_id": job_id, "status": "COMPLETED"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = AICoreClient(
            base_url="http://fake-ai-core",
            service_token="secret-token",
            client=http_client,
        )

        data = await client.get_job(job_id)
        assert data["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_ai_core_acknowledge_results():
    """Verify acknowledge_results sends POST /ack."""
    job_id = "c84dfb50-f331-4c12-88f5-3c1a3e6015aa"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"http://fake-ai-core/v1/jobs/{job_id}/results/ack"
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = AICoreClient(
            base_url="http://fake-ai-core",
            service_token="secret-token",
            client=http_client,
        )

        ack_res = await client.acknowledge_results(job_id)
        assert ack_res is True


@pytest.mark.asyncio
async def test_ai_core_cancel_job():
    """Verify cancel_job sends POST /cancel."""
    job_id = "c84dfb50-f331-4c12-88f5-3c1a3e6015aa"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"http://fake-ai-core/v1/jobs/{job_id}/cancel"
        return httpx.Response(200, json={"status": "CANCELLED"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = AICoreClient(
            base_url="http://fake-ai-core",
            service_token="secret-token",
            client=http_client,
        )

        res = await client.cancel_job(job_id)
        assert res["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_generation_service_dispatches_job_to_ai_core():
    """Verify GenerationService automatically calls AICoreClient and transitions album to QUEUED."""
    from io import BytesIO
    from fastapi import UploadFile
    from app.schemas.generation import GenerationRequestForm
    from tests.test_generations import InMemoryAlbumRepository, InMemoryStorageService, _make_user, FAKE_USER_ID

    ai_job_uuid = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "job_id": str(ai_job_uuid),
                "status": "QUEUED",
                "requested_image_count": 10,
                "status_url": f"/v1/jobs/{ai_job_uuid}",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        ai_client = AICoreClient(
            base_url="http://fake-ai-core",
            service_token="secret",
            client=http_client,
        )
        album_repo = InMemoryAlbumRepository()
        storage = InMemoryStorageService()
        service = GenerationService(
            album_repo=album_repo,
            storage=storage,
            ai_client=ai_client,
        )

        form = GenerationRequestForm(
            age=25,
            height=175,
            gender="m",
            situation="office",
            styles="minimalism",
            shoes="loafers",
            impressions="confident",
        )
        face_file = UploadFile(filename="face.jpg", file=BytesIO(b"\xff\xd8\xff\xe0fake-jpeg"))
        face_file.headers = {"content-type": "image/jpeg"}
        body_file = UploadFile(filename="body.jpg", file=BytesIO(b"\xff\xd8\xff\xe0fake-jpeg"))
        body_file.headers = {"content-type": "image/jpeg"}

        response = await service.create_generation(
            user_id=FAKE_USER_ID,
            face_photo=face_file,
            body_photo=body_file,
            form=form,
        )

        assert response.status == "QUEUED"
        # Album in repo updated to QUEUED and has ai_job_id
        assert len(album_repo.albums) == 1
        album = list(album_repo.albums.values())[0]
        assert album.status == "QUEUED"
        assert album.ai_job_id == ai_job_uuid

