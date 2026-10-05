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

os.environ.setdefault("SECRET_KEY", "pytest-secret-key-for-test-execution-only-32ch")
os.environ.setdefault("AI_CORE_SERVICE_TOKEN", "pytest-ai-core-service-token-for-tests")
os.environ.setdefault("AI_CORE_WEBHOOK_SECRET", "pytest-ai-core-webhook-secret-for-tests")

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

    async def get_by_ai_job_id(self, ai_job_id: uuid.UUID):
        for album in self.albums.values():
            if getattr(album, "ai_job_id", None) == ai_job_id:
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

    async def atomic_claim_for_download(self, album_id: uuid.UUID) -> bool:
        """Fake: atomically claim album for download. Returns True if status was PROCESSING."""
        album = self.albums.get(album_id)
        if album and album.status == "PROCESSING":
            album.status = "DOWNLOADING"
            return True
        return False


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
    """COMPLETED webhook triggers atomic_claim_for_download and schedules background task.

    The actual _download_and_store_results function is mocked because it opens
    a real AsyncSessionLocal (no PostgreSQL available in unit tests). We verify
    that the endpoint returns 200, the album is claimed (status -> DOWNLOADING),
    and the background task was scheduled with the correct arguments.
    """
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

    # Track calls to the background task without actually running it
    called_with = {}

    async def fake_download_and_store(album_id, job_uuid, ai_client):
        called_with["album_id"] = album_id
        called_with["job_uuid"] = job_uuid
        # Simulate successful completion
        album.status = "COMPLETED"

    import app.api.v1.endpoints.internal as internal_module
    monkeypatch.setattr(internal_module, "_download_and_store_results", fake_download_and_store)

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

            # atomic_claim_for_download should have transitioned PROCESSING -> DOWNLOADING
            # (BackgroundTasks in ASGI test mode run synchronously after response)
            assert called_with.get("album_id") == album_id
            assert called_with.get("job_uuid") == gen_id
            # After fake background task ran, album should be COMPLETED
            assert album.status == "COMPLETED"
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


@pytest.mark.asyncio
async def test_ai_events_webhook_idempotency(fake_repos, current_user):
    """Calling COMPLETED on an already COMPLETED album should return 200 without error."""
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    album_id = uuid.uuid4()
    album = Album(
        id=album_id,
        user_id=current_user.id,
        title="Офис",
        generation_id=gen_id,
        status="COMPLETED",
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
                "status": "COMPLETED",
            }).encode("utf-8")
            headers = generate_hmac_headers(payload)

            resp = await client.post("/api/v1/internal/ai-events", content=payload, headers=headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "already_finalized"
            assert album.status == "COMPLETED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ai_events_find_by_ai_job_id(fake_repos, current_user):
    """When webhook uses an external ai_job_id different from generation_id, album is found."""
    album_repo, storage, ai_client = fake_repos
    gen_id = uuid.uuid4()
    ai_job_id = uuid.uuid4()
    album_id = uuid.uuid4()
    album = Album(
        id=album_id,
        user_id=current_user.id,
        title="Вечер",
        generation_id=gen_id,
        ai_job_id=ai_job_id,
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
            # Send webhook using ai_job_id
            payload = json.dumps({
                "job_id": str(ai_job_id),
                "status": "PROCESSING",
            }).encode("utf-8")
            headers = generate_hmac_headers(payload)

            resp = await client.post("/api/v1/internal/ai-events", content=payload, headers=headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
            assert album.status == "PROCESSING"
    finally:
        app.dependency_overrides.clear()

