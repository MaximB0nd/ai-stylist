import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from internal.artifact_service.app import create_app
from internal.artifact_service.config import Settings
from internal.artifact_service.storage import Storage


ARTIFACT_ID = "01J8Z8Y7W6V5T4S3R2Q1P0N9B1"


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (4, 3), "blue").save(output, format="PNG")
    return output.getvalue()


def expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


@pytest.fixture
def real_storage():
    if not os.getenv("ARTIFACT_S3_ENDPOINT"):
        pytest.skip("ARTIFACT_S3_ENDPOINT is required for real S3 integration tests")
    settings = Settings(
        source_origin="http://source.test",
        public_base_url="http://artifact.test",
        bucket=f"test-artifacts-{secrets.token_hex(8)}",
    )
    storage = Storage(settings)
    yield settings, storage
    response = storage.client.list_objects_v2(Bucket=settings.bucket)
    for item in response.get("Contents", []):
        storage.client.delete_object(Bucket=settings.bucket, Key=item["Key"])
    storage.client.delete_bucket(Bucket=settings.bucket)


def test_import_and_restart_persist_deleted_state(real_storage):
    settings, storage = real_storage
    calls = []

    def source(request: httpx.Request):
        calls.append(request.url)
        return httpx.Response(200, content=png_bytes())

    payload = {"source_url": "http://source.test/photo", "max_size_bytes": 1024, "expires_at": expiry()}
    with TestClient(create_app(settings, storage, httpx.MockTransport(source))) as client:
        first = client.post(f"/internal/v1/artifacts/{ARTIFACT_ID}/import", json=payload)
        assert first.status_code == 201, first.text
        assert first.json()["url"].endswith(f"/{ARTIFACT_ID}/content")
        assert client.post(f"/internal/v1/artifacts/{ARTIFACT_ID}/import", json=payload).status_code == 200
        assert len(calls) == 1
        assert client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content").content == png_bytes()
        assert client.delete(f"/internal/v1/artifacts/{ARTIFACT_ID}").status_code == 204

    with TestClient(create_app(settings, Storage(settings))) as restarted:
        assert restarted.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content").status_code == 404
        assert restarted.post(f"/internal/v1/artifacts/{ARTIFACT_ID}/import", json=payload).status_code == 409


@pytest.mark.asyncio
async def test_multipart_stream_round_trip(real_storage):
    _, storage = real_storage
    await storage.ensure_bucket()
    data = secrets.token_bytes(5 * 1024 * 1024 + 100)

    async def chunks():
        for offset in range(0, len(data), 64 * 1024):
            yield data[offset : offset + 64 * 1024]

    key, collected, checksum = await storage.upload_stream(
        ARTIFACT_ID, chunks(), len(data), "application/octet-stream"
    )
    assert collected == data
    assert checksum.startswith("sha256:")
    obj = await storage.open_object(key)
    try:
        assert await asyncio.to_thread(obj["Body"].read) == data
    finally:
        obj["Body"].close()


@pytest.mark.asyncio
async def test_delete_during_put_blocks_late_publication(real_storage):
    settings, storage = real_storage
    await storage.ensure_bucket()
    app = create_app(settings, storage)
    sent_first_chunk = asyncio.Event()
    resume = asyncio.Event()
    body = png_bytes()

    async def request_body():
        yield body[:8]
        sent_first_chunk.set()
        await resume.wait()
        yield body[8:]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://artifact.test") as client:
        upload = asyncio.create_task(
            client.put(
                f"/internal/v1/artifacts/{ARTIFACT_ID}/content",
                content=request_body(),
                headers={"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()},
            )
        )
        await asyncio.wait_for(sent_first_chunk.wait(), timeout=10)
        assert (await client.delete(f"/internal/v1/artifacts/{ARTIFACT_ID}")).status_code == 204
        resume.set()
        assert (await upload).status_code == 409
        assert (await client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content")).status_code == 404


@pytest.mark.asyncio
async def test_expired_bytes_are_physically_removed(real_storage):
    settings, storage = real_storage
    await storage.ensure_bucket()
    key = f"staging/{ARTIFACT_ID}/expired"
    storage.client.put_object(Bucket=settings.bucket, Key=key, Body=b"photo")
    await storage.put_state(
        ARTIFACT_ID,
        {
            "status": "PUBLISHED",
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "blob_key": key,
        },
    )
    await storage.cleanup_expired()
    assert await storage.get_state(ARTIFACT_ID) is None
    assert storage.client.list_objects_v2(Bucket=settings.bucket).get("KeyCount", 0) == 0
