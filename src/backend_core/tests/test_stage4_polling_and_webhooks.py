from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path

import sys
import time
import uuid

backend_core_dir = Path(__file__).resolve().parent.parent
if str(backend_core_dir) not in sys.path:
    sys.path.insert(0, str(backend_core_dir))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-execution")

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings

from app.core.dependencies import (
    get_ai_core_client,
    get_album_repository,
    get_current_user,
    get_storage_service,
    get_user_repository,
)
from app.main import app
from app.models.album import Album
from app.models.photo import Photo
from app.models.user import User


class FakeAlbumRepository:
    def __init__(self):
        self.albums = {}

    async def get_by_generation_id(self, generation_id: uuid.UUID):
        for album in self.albums.values():
            if album.generation_id == generation_id:
                return album
        return None

    async def get_by_id(self, album_id: uuid.UUID):
        return self.albums.get(album_id)

    async def update_status(self, album_id: uuid.UUID, status: str, error_message: str = None):
        album = self.albums.get(album_id)
        if album:
            album.status = status
            album.error_message = error_message
            album.updated_at = datetime.now(timezone.utc)
            return album
        return None

    async def add_photos(self, album_id: uuid.UUID, photos_data: list[dict]):
        album = self.albums.get(album_id)
        if album:
            if not hasattr(album, "photos") or album.photos is None:
                album.photos = []
            for p in photos_data:
                photo_obj = Photo(
                    id=uuid.uuid4(),
                    album_id=album_id,
                    order_index=p["order_index"],
                    object_key=p["object_key"],
                    is_cover=p.get("is_cover", False),
                    is_favorite=p.get("is_favorite", False),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                album.photos.append(photo_obj)
            return album.photos
        return []



class FakeStorageService:
    def __init__(self):
        self.uploaded_files = {}

    async def upload_bytes(self, object_key: str, data: bytes, content_type: str = "application/octet-stream"):
        self.uploaded_files[object_key] = (data, content_type)
        return object_key


class FakeAICoreClient:
    def __init__(self):
        self.acknowledged_jobs = []
        self.job_details = {}

    async def get_job(self, job_id: uuid.UUID):
        return self.job_details.get(
            job_id,
            {
                "id": str(job_id),
                "status": "COMPLETED",
                "results": [],
            },
        )

    async def acknowledge_results(self, job_id: uuid.UUID):
        self.acknowledged_jobs.append(job_id)
        return {"status": "ok"}


@pytest.fixture
def fake_repos():
    album_repo = FakeAlbumRepository()
    storage = FakeStorageService()
    ai_client = FakeAICoreClient()
    return album_repo, storage, ai_client


@pytest.fixture
def current_user():
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        name="Test User",
        password_hash="hash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def other_user():
    return User(
        id=uuid.uuid4(),
        email="other@example.com",
        name="Other User",
        password_hash="hash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )



def generate_hmac_headers(body: bytes, secret: str = None, timestamp: float = None):
    sec = secret or settings.AI_CORE_WEBHOOK_SECRET
    ts = str(timestamp if timestamp is not None else time.time())
    message = f"{ts}.{body.decode('utf-8')}".encode("utf-8")
    sig = hmac.new(sec.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return {
        "X-AI-Core-Timestamp": ts,
        "X-AI-Core-Signature": sig,
    }


# ==============================================================================
# 1. Status polling tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_generation_status_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/generations/{uuid.uuid4()}/status")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_generation_status_not_found(fake_repos, current_user):
    album_repo, storage, ai_client = fake_repos
    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_current_user] = lambda: current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/generations/{uuid.uuid4()}/status")
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Generation not found."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_generation_status_forbidden_other_user(fake_repos, current_user, other_user):
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    album_id = uuid.uuid4()
    # Album belongs to other_user
    album = Album(
        id=album_id,
        user_id=other_user.id,
        title="Офис",
        generation_id=gen_id,
        status="PROCESSING",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    album_repo.albums[album_id] = album

    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_current_user] = lambda: current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/generations/{gen_id}/status")
            assert resp.status_code == 403
            assert resp.json()["detail"] == "You do not have access to this generation."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_generation_status_processing_and_completed(fake_repos, current_user):
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    album_id = uuid.uuid4()
    album = Album(
        id=album_id,
        user_id=current_user.id,
        title="Улица",
        generation_id=gen_id,
        status="PROCESSING",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    album_repo.albums[album_id] = album

    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_current_user] = lambda: current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # While PROCESSING -> album_id is None
            resp = await client.get(f"/api/v1/generations/{gen_id}/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["generation_id"] == str(gen_id)
            assert data["status"] == "PROCESSING"
            assert data["album_id"] is None

            # Mark as COMPLETED -> album_id is revealed
            album.status = "COMPLETED"
            resp2 = await client.get(f"/api/v1/generations/{gen_id}/status")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["status"] == "COMPLETED"
            assert data2["album_id"] == str(album_id)
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 2. Webhook receiver tests (POST /api/v1/internal/ai-events)
# ==============================================================================

@pytest.mark.asyncio
async def test_ai_events_webhook_auth_failures(fake_repos):
    album_repo, storage, ai_client = fake_repos
    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_storage_service] = lambda: storage
    app.dependency_overrides[get_ai_core_client] = lambda: ai_client

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = json.dumps({"job_id": str(uuid.uuid4()), "status": "PROCESSING"}).encode("utf-8")

            # Missing headers
            resp = await client.post("/api/v1/internal/ai-events", content=payload)
            assert resp.status_code == 401

            # Expired timestamp (drift > 300s)
            expired_headers = generate_hmac_headers(payload, timestamp=time.time() - 350)
            resp = await client.post("/api/v1/internal/ai-events", content=payload, headers=expired_headers)
            assert resp.status_code == 401
            assert "expired" in resp.json()["detail"].lower()

            # Wrong secret HMAC
            bad_sig_headers = generate_hmac_headers(payload, secret="wrong-secret")
            resp = await client.post("/api/v1/internal/ai-events", content=payload, headers=bad_sig_headers)
            assert resp.status_code == 401
            assert "Invalid HMAC-SHA256 signature" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ai_events_processing_event(fake_repos, current_user):
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    album_id = uuid.uuid4()
    album = Album(
        id=album_id,
        user_id=current_user.id,
        title="Офис",
        generation_id=gen_id,
        status="QUEUED",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    album_repo.albums[album_id] = album

    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_storage_service] = lambda: storage
    app.dependency_overrides[get_ai_core_client] = lambda: ai_client

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = json.dumps({
                "job_id": str(gen_id),
                "status": "PROCESSING",
                "progress_percent": 30,
            }).encode("utf-8")
            headers = generate_hmac_headers(payload)

            resp = await client.post("/api/v1/internal/ai-events", content=payload, headers=headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
            assert album.status == "PROCESSING"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ai_events_failed_event(fake_repos, current_user):
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    album_id = uuid.uuid4()
    album = Album(
        id=album_id,
        user_id=current_user.id,
        title="Вечер",
        generation_id=gen_id,
        status="PROCESSING",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    album_repo.albums[album_id] = album

    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_storage_service] = lambda: storage
    app.dependency_overrides[get_ai_core_client] = lambda: ai_client

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = json.dumps({
                "job_id": str(gen_id),
                "status": "FAILED",
                "error": {"code": "FACE_DETECTION_FAILED", "message": "No face found in photo"},
            }).encode("utf-8")
            headers = generate_hmac_headers(payload)

            resp = await client.post("/api/v1/internal/ai-events", content=payload, headers=headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "failed"
            assert album.status == "FAILED"
            assert "FACE_DETECTION_FAILED" in album.error_message
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ai_events_completed_with_download_and_ack(fake_repos, current_user, monkeypatch):
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    album_id = uuid.uuid4()
    album = Album(
        id=album_id,
        user_id=current_user.id,
        title="Улица",
        generation_id=gen_id,
        status="PROCESSING",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    album_repo.albums[album_id] = album

    # Mock job results in ai_client
    image_bytes = b"fake-webp-image-bytes-stage-4"
    img_sha256 = hashlib.sha256(image_bytes).hexdigest()

    ai_client.job_details[gen_id] = {
        "id": str(gen_id),
        "status": "COMPLETED",
        "results": [
            {
                "order_index": 0,
                "download_url": "https://temp-s3.example.com/look_00.webp",
                "checksum_sha256": f"sha256:{img_sha256}",
            },
            {
                "order_index": 1,
                "download_url": "https://temp-s3.example.com/look_01.webp",
                "checksum_sha256": f"sha256:{img_sha256}",
            },
        ],
    }

    # Mock httpx.AsyncClient.get for downloading images from temp S3
    class MockDownloadResponse:
        def __init__(self, content):
            self.content = content
            self.status_code = 200

    original_get = AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        if "temp-s3.example.com" in str(url):
            return MockDownloadResponse(image_bytes)
        return await original_get(self, url, *args, **kwargs)

    monkeypatch.setattr(AsyncClient, "get", mock_get)

    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_storage_service] = lambda: storage
    app.dependency_overrides[get_ai_core_client] = lambda: ai_client

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = json.dumps({
                "job_id": str(gen_id),
                "status": "COMPLETED",
            }).encode("utf-8")
            headers = generate_hmac_headers(payload)

            resp = await client.post("/api/v1/internal/ai-events", content=payload, headers=headers)
            assert resp.status_code == 200
            assert resp.json()["success"] is True

            # Check album status is COMPLETED
            assert album.status == "COMPLETED"

            # Check photos were saved in storage service
            expected_key_0 = f"albums/{album_id}/look_00.webp"
            expected_key_1 = f"albums/{album_id}/look_01.webp"
            assert expected_key_0 in storage.uploaded_files
            assert expected_key_1 in storage.uploaded_files
            assert storage.uploaded_files[expected_key_0][0] == image_bytes

            # Check photos were added to album
            assert len(album.photos) == 2
            assert album.photos[0].is_cover is True
            assert album.photos[1].is_cover is False

            # Check ACK was sent to AI Core client
            assert gen_id in ai_client.acknowledged_jobs
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 3. Legacy Webhook endpoint tests (POST /api/v1/internal/generations/{id}/complete)
# ==============================================================================

@pytest.mark.asyncio
async def test_legacy_complete_webhook(fake_repos, current_user):
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    album_id = uuid.uuid4()
    album = Album(
        id=album_id,
        user_id=current_user.id,
        title="Офис",
        generation_id=gen_id,
        status="PROCESSING",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    album_repo.albums[album_id] = album

    app.dependency_overrides[get_album_repository] = lambda: album_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "photos": [
                    {"order_index": 0, "object_key": f"albums/{album_id}/look_00.webp"},
                    {"order_index": 1, "object_key": f"albums/{album_id}/look_01.webp"},
                ]
            }

            # 401 without token
            resp_unauth = await client.post(
                f"/api/v1/internal/generations/{gen_id}/complete",
                json=payload,
            )
            assert resp_unauth.status_code == 401

            # 200 with valid X-Internal-Token
            resp = await client.post(
                f"/api/v1/internal/generations/{gen_id}/complete",
                json=payload,
                headers={"X-Internal-Token": settings.AI_CORE_SERVICE_TOKEN},
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert album.status == "COMPLETED"
            assert len(album.photos) == 2
    finally:
        app.dependency_overrides.clear()
