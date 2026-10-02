"""In-memory tests for GET /api/v1/albums and GET /api/v1/albums/{album_id}.

All dependencies (AlbumRepository, StorageService, UserRepository) are mocked
in-memory — no database or MinIO required.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import AsyncGenerator, Dict, List, Optional
import uuid

import httpx
from jose import jwt
import pytest

# Ensure backend_core directory is on sys.path
backend_core_dir = Path(__file__).resolve().parent.parent
if str(backend_core_dir) not in sys.path:
    sys.path.insert(0, str(backend_core_dir))

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-execution")

from app.core.config import settings
from app.core.dependencies import (
    get_album_repository,
    get_album_service,
    get_storage_service,
    get_user_repository,
)
from app.db.repositories.album_repository import AlbumRepository
from app.db.repositories.user_repository import UserRepository
from app.main import app
from app.models.album import Album
from app.models.photo import Photo
from app.models.user import User
from app.services.album_service import AlbumService
from app.services.storage_service import StorageService


# =============================================================================
# In-memory mocks
# =============================================================================


class InMemoryUserRepository(UserRepository):
    """In-memory user store for test isolation."""

    def __init__(self) -> None:
        self.users: Dict[uuid.UUID, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        clean = email.strip().lower()
        for u in self.users.values():
            if u.email == clean:
                return u
        return None

    async def create(self, name: str, email: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid.uuid4(),
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.users[user.id] = user
        return user


class InMemoryAlbumRepository(AlbumRepository):
    """In-memory album store pre-seeded with test data."""

    def __init__(self) -> None:
        self.albums: Dict[uuid.UUID, Album] = {}

    async def get_by_id_with_photos(self, album_id: uuid.UUID) -> Optional[Album]:
        return self.albums.get(album_id)

    async def get_user_album_ids(self, user_id: uuid.UUID) -> List[uuid.UUID]:
        return [
            a.id
            for a in sorted(
                self.albums.values(), key=lambda a: a.created_at, reverse=True
            )
            if a.user_id == user_id
        ]

    async def get_by_generation_id(self, generation_id: uuid.UUID) -> Optional[Album]:
        return next(
            (a for a in self.albums.values() if a.generation_id == generation_id),
            None,
        )

    async def update_status(
        self,
        album_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None,
        ai_job_id: Optional[uuid.UUID] = None,
    ) -> Optional[Album]:
        album = self.albums.get(album_id)
        if not album:
            return None
        album.status = status
        if error_message is not None:
            album.error_message = error_message
        if ai_job_id is not None:
            album.ai_job_id = ai_job_id
        return album

    async def add_photos(
        self, album_id: uuid.UUID, photos_data: List[dict]
    ) -> List[Photo]:
        album = self.albums.get(album_id)
        if not album:
            return []
        photos = [
            Photo(
                id=uuid.uuid4(),
                album_id=album_id,
                order_index=item["order_index"],
                object_key=item["object_key"],
                is_cover=item.get("is_cover", False),
                is_favorite=item.get("is_favorite", False),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            for item in photos_data
        ]
        album.photos.extend(photos)
        return photos

    async def create_album(self, **kwargs) -> Album:
        now = datetime.now(timezone.utc)
        kwargs.setdefault("status", "VALIDATING")
        album = Album(
            id=uuid.uuid4(),
            created_at=now,
            updated_at=now,
            total_photos=10,
            is_archived=False,
            photos=[],
            **kwargs,
        )
        self.albums[album.id] = album
        return album

    def seed_album(
        self,
        user_id: uuid.UUID,
        album_id: Optional[uuid.UUID] = None,
        num_photos: int = 3,
        is_archived: bool = False,
        situation: str = "office",
    ) -> Album:
        """Helper to add a pre-built album with photos to the store."""
        aid = album_id or uuid.uuid4()
        now = datetime.now(timezone.utc)

        photos = []
        for i in range(num_photos):
            photo = Photo(
                id=uuid.uuid4(),
                album_id=aid,
                order_index=i,
                object_key=f"albums/{aid}/look_{i:02d}.webp",
                is_cover=(i == 0),
                is_favorite=False,
                created_at=now,
                updated_at=now,
            )
            photos.append(photo)

        album = Album(
            id=aid,
            user_id=user_id,
            generation_id=uuid.uuid4(),
            title="Офис",
            situation=situation,
            styles=["minimalism"],
            shoes=["loafers"],
            impressions=["confident"],
            user_age=25,
            user_height=175,
            gender="m",
            source_face_key=f"sources/{user_id}/{aid}/face.jpg",
            source_body_key=f"sources/{user_id}/{aid}/body.jpg",
            total_photos=num_photos,
            is_archived=is_archived,
            created_at=now,
            updated_at=now,
            photos=photos,
        )
        self.albums[aid] = album
        return album


class InMemoryStorageService(StorageService):
    """In-memory storage — returns deterministic presigned URLs."""

    def __init__(self) -> None:
        self.presigned_ttl = 3600

    async def upload_file(self, object_key: str, file) -> str:
        return object_key

    async def upload_bytes(self, object_key: str, data: bytes, content_type: str = "image/webp") -> str:
        return object_key

    def presigned_url(self, object_key: str) -> str:
        return f"https://fake-minio.local/{object_key}?signed=1"


# =============================================================================
# Fixtures
# =============================================================================

USER_A_ID = uuid.uuid4()
USER_B_ID = uuid.uuid4()


def _make_user(user_id: uuid.UUID, email: str = "album@test.local") -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=user_id,
        name="Test User",
        email=email,
        password_hash="$2b$12$fakehashvalue",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _make_token(user_id: uuid.UUID) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime(2099, 1, 1, tzinfo=timezone.utc)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth_header(user_id: uuid.UUID) -> Dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    repo = InMemoryUserRepository()
    repo.users[USER_A_ID] = _make_user(USER_A_ID, "usera@test.local")
    repo.users[USER_B_ID] = _make_user(USER_B_ID, "userb@test.local")
    return repo


@pytest.fixture
def album_repo() -> InMemoryAlbumRepository:
    return InMemoryAlbumRepository()


@pytest.fixture
def storage() -> InMemoryStorageService:
    return InMemoryStorageService()


@pytest.fixture
async def client(
    user_repo: InMemoryUserRepository,
    album_repo: InMemoryAlbumRepository,
    storage: InMemoryStorageService,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_storage_service] = lambda: storage
    app.dependency_overrides[get_album_service] = lambda: AlbumService(
        album_repo=album_repo, storage=storage
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# =============================================================================
# 1. GET /api/v1/albums — User album IDs
# =============================================================================


async def test_get_albums_empty(client: httpx.AsyncClient):
    """User with no albums gets an empty list with total=0."""
    resp = await client.get("/api/v1/albums", headers=_auth_header(USER_A_ID))
    assert resp.status_code == 200
    body = resp.json()
    assert body["album_ids"] == []
    assert body["total"] == 0


async def test_get_albums_returns_own_ids(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """User sees only their own album IDs."""
    a1 = album_repo.seed_album(USER_A_ID)
    a2 = album_repo.seed_album(USER_A_ID)
    _b1 = album_repo.seed_album(USER_B_ID)  # other user's album

    resp = await client.get("/api/v1/albums", headers=_auth_header(USER_A_ID))
    assert resp.status_code == 200
    body = resp.json()
    returned_ids = set(body["album_ids"])
    assert str(a1.id) in returned_ids or a1.id in [uuid.UUID(x) for x in returned_ids]
    assert body["total"] == 2


async def test_get_albums_isolation_between_users(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """User B cannot see User A's albums."""
    album_repo.seed_album(USER_A_ID)
    album_repo.seed_album(USER_A_ID)

    resp = await client.get("/api/v1/albums", headers=_auth_header(USER_B_ID))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_get_albums_requires_auth(client: httpx.AsyncClient):
    """GET /albums without token → 401."""
    resp = await client.get("/api/v1/albums")
    assert resp.status_code == 401


# =============================================================================
# 2. GET /api/v1/albums/{album_id} — Album detail with photos
# =============================================================================


async def test_get_album_detail_success(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Owner can retrieve their album with photos and presigned URLs."""
    album = album_repo.seed_album(USER_A_ID, num_photos=3)

    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(album.id)
    assert body["title"] == "Офис"
    assert body["situation"] == "office"
    assert body["styles"] == ["minimalism"]
    assert body["shoes"] == ["loafers"]
    assert body["impressions"] == ["confident"]
    assert body["total_photos"] == 3
    assert body["is_archived"] is False
    assert "created_at" in body
    # Check photos
    assert len(body["photos"]) == 3
    for photo in body["photos"]:
        assert "id" in photo
        assert "order_index" in photo
        assert "url" in photo
        assert "fake-minio.local" in photo["url"]
        assert "signed=1" in photo["url"]


async def test_get_album_detail_photo_urls_contain_object_keys(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Presigned URLs should contain the original object keys."""
    album = album_repo.seed_album(USER_A_ID, num_photos=2)

    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
    )
    assert resp.status_code == 200
    photos = resp.json()["photos"]
    for photo in photos:
        assert f"albums/{album.id}" in photo["url"]


async def test_get_album_detail_photos_ordered(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Photos should be returned with ascending order_index."""
    album = album_repo.seed_album(USER_A_ID, num_photos=5)

    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
    )
    photos = resp.json()["photos"]
    indices = [p["order_index"] for p in photos]
    assert indices == sorted(indices)


async def test_get_album_detail_no_photos(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Album with zero photos returns empty photos array."""
    album = album_repo.seed_album(USER_A_ID, num_photos=0)

    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
    )
    assert resp.status_code == 200
    assert resp.json()["photos"] == []


async def test_get_album_detail_archived(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Archived album is still retrievable, is_archived=true in response."""
    album = album_repo.seed_album(USER_A_ID, is_archived=True)

    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
    )
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is True


# =============================================================================
# 3. Ownership enforcement (403 Forbidden)
# =============================================================================


async def test_get_album_forbidden_for_other_user(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """User B cannot access User A's album → 403."""
    album = album_repo.seed_album(USER_A_ID)

    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_B_ID)
    )
    assert resp.status_code == 403
    assert "forbidden" in resp.json()["detail"].lower()


async def test_get_album_forbidden_does_not_leak_data(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """403 response should not contain album data."""
    album = album_repo.seed_album(USER_A_ID)

    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_B_ID)
    )
    body = resp.json()
    assert "photos" not in body
    assert "title" not in body


# =============================================================================
# 4. Not Found (404)
# =============================================================================


async def test_get_album_not_found(client: httpx.AsyncClient):
    """Non-existent album ID → 404."""
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/albums/{fake_id}", headers=_auth_header(USER_A_ID)
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_get_album_invalid_uuid(client: httpx.AsyncClient):
    """Invalid UUID in path → 422."""
    resp = await client.get(
        "/api/v1/albums/not-a-uuid", headers=_auth_header(USER_A_ID)
    )
    assert resp.status_code == 422


# =============================================================================
# 5. Authentication requirements
# =============================================================================


async def test_get_album_detail_requires_auth(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """GET /albums/{id} without token → 401."""
    album = album_repo.seed_album(USER_A_ID)
    resp = await client.get(f"/api/v1/albums/{album.id}")
    assert resp.status_code == 401


async def test_get_album_detail_invalid_token(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """GET /albums/{id} with bad JWT → 401."""
    album = album_repo.seed_album(USER_A_ID)
    resp = await client.get(
        f"/api/v1/albums/{album.id}",
        headers={"Authorization": "Bearer garbage.token.here"},
    )
    assert resp.status_code == 401


# =============================================================================
# 6. Response structure validation
# =============================================================================


async def test_album_detail_response_fields(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Verify all expected fields are present in album detail response."""
    album = album_repo.seed_album(USER_A_ID, num_photos=1)
    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
    )
    body = resp.json()
    expected_keys = {
        "id",
        "title",
        "situation",
        "styles",
        "shoes",
        "impressions",
        "created_at",
        "is_archived",
        "total_photos",
        "photos",
    }
    assert set(body.keys()) == expected_keys


async def test_album_photo_response_fields(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Verify each photo object has exactly id, order_index, url."""
    album = album_repo.seed_album(USER_A_ID, num_photos=2)
    resp = await client.get(
        f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
    )
    for photo in resp.json()["photos"]:
        assert set(photo.keys()) == {"id", "order_index", "url"}


async def test_user_album_ids_response_fields(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Verify GET /albums response has exactly album_ids and total."""
    album_repo.seed_album(USER_A_ID)
    resp = await client.get("/api/v1/albums", headers=_auth_header(USER_A_ID))
    assert set(resp.json().keys()) == {"album_ids", "total"}


# =============================================================================
# 7. Edge cases
# =============================================================================


async def test_multiple_albums_correct_total(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """total field should match the actual number of album_ids."""
    for _ in range(5):
        album_repo.seed_album(USER_A_ID)

    resp = await client.get("/api/v1/albums", headers=_auth_header(USER_A_ID))
    body = resp.json()
    assert body["total"] == 5
    assert len(body["album_ids"]) == 5


async def test_album_different_situations(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Albums with different situations are all retrievable."""
    for situation in ["street", "study", "office", "evening"]:
        album = album_repo.seed_album(USER_A_ID, situation=situation)
        resp = await client.get(
            f"/api/v1/albums/{album.id}", headers=_auth_header(USER_A_ID)
        )
        assert resp.status_code == 200
        assert resp.json()["situation"] == situation


async def test_album_repo_get_by_generation_id(album_repo: InMemoryAlbumRepository):
    """Test retrieving album by generation_id."""
    gen_id = uuid.uuid4()
    album = await album_repo.create_album(
        user_id=USER_A_ID,
        generation_id=gen_id,
        title="Test",
        situation="office",
        styles=["classic"],
        shoes=["loafers"],
        impressions=["elegant"],
    )
    found = await album_repo.get_by_generation_id(gen_id)
    assert found is not None
    assert found.id == album.id
    assert found.status == "VALIDATING"

    not_found = await album_repo.get_by_generation_id(uuid.uuid4())
    assert not_found is None


async def test_album_repo_update_status(album_repo: InMemoryAlbumRepository):
    """Test updating album status, error_message and ai_job_id."""
    gen_id = uuid.uuid4()
    album = await album_repo.create_album(
        user_id=USER_A_ID,
        generation_id=gen_id,
        title="Test",
        situation="office",
        styles=["classic"],
        shoes=["loafers"],
        impressions=["elegant"],
    )
    job_id = uuid.uuid4()
    updated = await album_repo.update_status(
        album_id=album.id,
        status="PROCESSING",
        ai_job_id=job_id,
    )
    assert updated is not None
    assert updated.status == "PROCESSING"
    assert updated.ai_job_id == job_id

    # Test updating to FAILED with error
    failed = await album_repo.update_status(
        album_id=album.id,
        status="FAILED",
        error_message="AI generation timeout",
    )
    assert failed is not None
    assert failed.status == "FAILED"
    assert failed.error_message == "AI generation timeout"


async def test_album_repo_add_photos(album_repo: InMemoryAlbumRepository):
    """Test batch adding photos to an album."""
    gen_id = uuid.uuid4()
    album = await album_repo.create_album(
        user_id=USER_A_ID,
        generation_id=gen_id,
        title="Test",
        situation="office",
        styles=["classic"],
        shoes=["loafers"],
        impressions=["elegant"],
    )
    photos_data = [
        {"order_index": 0, "object_key": "albums/test/0.webp", "is_cover": True},
        {"order_index": 1, "object_key": "albums/test/1.webp", "is_favorite": True},
    ]
    added = await album_repo.add_photos(album.id, photos_data)
    assert len(added) == 2
    assert added[0].order_index == 0
    assert added[0].is_cover is True
    assert added[1].order_index == 1
    assert added[1].is_favorite is True
    assert len(album.photos) == 2

