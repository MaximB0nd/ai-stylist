"""In-memory tests for POST /api/v1/generations endpoint and GenerationService.

All dependencies (AlbumRepository, StorageService, UserRepository) are mocked
in-memory — no database or MinIO required.
"""

from datetime import datetime, timezone
from io import BytesIO
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
    get_generation_service,
    get_storage_service,
    get_user_repository,
)
from app.db.repositories.album_repository import AlbumRepository
from app.db.repositories.user_repository import UserRepository
from app.main import app
from app.models.album import Album
from app.models.user import User
from app.services.generation_service import GenerationService
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
    """In-memory album store — records every create_album call."""

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

    async def create_album(self, **kwargs) -> Album:
        now = datetime.now(timezone.utc)
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


class InMemoryStorageService(StorageService):
    """In-memory storage — tracks uploaded files, returns fake presigned URLs."""

    def __init__(self) -> None:
        self.uploads: Dict[str, bytes] = {}

    async def upload_file(self, object_key: str, file) -> str:
        content = await file.read()
        self.uploads[object_key] = content
        # Reset file position for potential re-read
        if hasattr(file, "seek"):
            await file.seek(0)
        return object_key

    def presigned_url(self, object_key: str) -> str:
        return f"https://fake-minio.local/{object_key}?signed=1"


class FailingStorageService(StorageService):
    """Storage mock that always raises on upload — simulates MinIO outage."""

    def __init__(self) -> None:
        pass

    async def upload_file(self, object_key: str, file) -> str:
        raise ConnectionError("MinIO is unreachable")

    def presigned_url(self, object_key: str) -> str:
        return ""


# =============================================================================
# Fixtures
# =============================================================================

FAKE_USER_ID = uuid.uuid4()


def _make_user(user_id: uuid.UUID = FAKE_USER_ID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=user_id,
        name="Test User",
        email="gen@test.local",
        password_hash="$2b$12$fakehashvalue",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _make_token(user_id: uuid.UUID = FAKE_USER_ID) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime(2099, 1, 1, tzinfo=timezone.utc)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth_header(user_id: uuid.UUID = FAKE_USER_ID) -> Dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _fake_image(content_type: str = "image/jpeg", filename: str = "photo.jpg") -> tuple:
    """Return (filename, BytesIO, content_type) tuple suitable for httpx file upload."""
    return (filename, BytesIO(b"\xff\xd8\xff\xe0fake-jpeg-bytes"), content_type)


VALID_FORM = {
    "age": "25",
    "height": "175",
    "gender": "m",
    "situation": "office",
    "styles": '["minimalism"]',
    "shoes": '["loafers"]',
    "impressions": '["confident"]',
}


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    repo = InMemoryUserRepository()
    repo.users[FAKE_USER_ID] = _make_user()
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
    app.dependency_overrides[get_generation_service] = lambda: GenerationService(
        album_repo=album_repo, storage=storage
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def failing_client(
    user_repo: InMemoryUserRepository,
    album_repo: InMemoryAlbumRepository,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client with a storage that always fails — for testing 502 behaviour."""
    failing_storage = FailingStorageService()
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    app.dependency_overrides[get_album_repository] = lambda: album_repo
    app.dependency_overrides[get_storage_service] = lambda: failing_storage
    app.dependency_overrides[get_generation_service] = lambda: GenerationService(
        album_repo=album_repo, storage=failing_storage
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# =============================================================================
# 1. Successful generation request (POST /api/v1/generations)
# =============================================================================


@pytest.mark.parametrize(
    "gender",
    ["m", "f"],
    ids=["male", "female"],
)
async def test_create_generation_success(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
    storage: InMemoryStorageService,
    gender: str,
):
    """Happy path — valid form + valid photos → 202 with generation_id."""
    form = {**VALID_FORM, "gender": gender}
    resp = await client.post(
        "/api/v1/generations",
        data=form,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "generation_id" in body
    assert body["status"] == "VALIDATING"
    assert "status_poll_url" in body
    # Album was persisted in memory
    assert len(album_repo.albums) == 1
    album = list(album_repo.albums.values())[0]
    assert album.user_id == FAKE_USER_ID
    assert album.situation == "office"
    assert album.gender == gender
    # Photos were uploaded
    assert len(storage.uploads) == 2


@pytest.mark.parametrize(
    "situation, expected_title",
    [
        ("street", "Улица"),
        ("study", "Учёба"),
        ("office", "Офис"),
        ("evening", "Вечер"),
    ],
    ids=["street", "study", "office", "evening"],
)
async def test_generation_title_from_situation(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
    situation: str,
    expected_title: str,
):
    """Album title is auto-generated from situation enum (Russian)."""
    form = {**VALID_FORM, "situation": situation}
    resp = await client.post(
        "/api/v1/generations",
        data=form,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 202
    album = list(album_repo.albums.values())[0]
    assert album.title == expected_title


async def test_generation_stores_age_and_height(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Verify age and height from form are persisted in the album record."""
    form = {**VALID_FORM, "age": "30", "height": "180"}
    resp = await client.post(
        "/api/v1/generations",
        data=form,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 202
    album = list(album_repo.albums.values())[0]
    assert album.user_age == 30
    assert album.user_height == 180


async def test_generation_stores_multi_select_fields(
    client: httpx.AsyncClient,
    album_repo: InMemoryAlbumRepository,
):
    """Verify that multi-select fields (styles, shoes, impressions) are stored."""
    form = {
        **VALID_FORM,
        "styles": '["minimalism", "classic"]',
        "shoes": '["sneakers", "boots"]',
        "impressions": '["confident", "elegant"]',
    }
    resp = await client.post(
        "/api/v1/generations",
        data=form,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 202
    album = list(album_repo.albums.values())[0]
    assert album.styles == ["minimalism", "classic"]
    assert album.shoes == ["sneakers", "boots"]
    assert album.impressions == ["confident", "elegant"]


async def test_generation_uploads_correct_keys(
    client: httpx.AsyncClient,
    storage: InMemoryStorageService,
):
    """Uploaded object keys follow the pattern sources/{user_id}/{gen_id}/face|body.ext."""
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(filename="portrait.png", content_type="image/png"),
            "body_photo": _fake_image(filename="body.webp", content_type="image/webp"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 202
    keys = list(storage.uploads.keys())
    assert len(keys) == 2
    face_key = [k for k in keys if "face" in k][0]
    body_key = [k for k in keys if "body" in k][0]
    assert face_key.startswith(f"sources/{FAKE_USER_ID}/")
    assert face_key.endswith(".png")
    assert body_key.startswith(f"sources/{FAKE_USER_ID}/")
    assert body_key.endswith(".webp")


# =============================================================================
# 2. Validation errors — form data
# =============================================================================


@pytest.mark.parametrize(
    "field, value, test_id",
    [
        ("age", "0", "age_too_low"),
        ("age", "151", "age_too_high"),
        ("height", "49", "height_too_low"),
        ("height", "301", "height_too_high"),
        ("gender", "x", "invalid_gender"),
        ("gender", "male", "gender_full_word"),
        ("situation", "beach", "invalid_situation"),
        ("styles", '[]', "styles_empty"),
        ("styles", '["minimalism","classic","casual"]', "styles_too_many"),
        ("styles", '["unknown_style"]', "styles_invalid_value"),
        ("shoes", '["sandals"]', "shoes_invalid_value"),
        ("impressions", '["boring"]', "impressions_invalid_value"),
        ("styles", "not-json", "styles_invalid_json"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
async def test_generation_form_validation_errors(
    client: httpx.AsyncClient,
    field: str,
    value: str,
    test_id: str,
):
    """Invalid form field values should return 400."""
    form = {**VALID_FORM, field: value}
    resp = await client.post(
        "/api/v1/generations",
        data=form,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 400, f"Expected 400 for {test_id}, got {resp.status_code}"


@pytest.mark.parametrize(
    "field, value",
    [
        ("age", "abc"),
        ("height", "xyz"),
    ],
    ids=["age_not_int", "height_not_int"],
)
async def test_generation_form_type_coercion_errors(
    client: httpx.AsyncClient,
    field: str,
    value: str,
):
    """Non-integer values for int fields are rejected by FastAPI at 422 (before Pydantic)."""
    form = {**VALID_FORM, field: value}
    resp = await client.post(
        "/api/v1/generations",
        data=form,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 422, f"Expected 422 for {field}={value}, got {resp.status_code}"


# =============================================================================
# 3. Photo validation errors
# =============================================================================


async def test_generation_invalid_content_type(client: httpx.AsyncClient):
    """Non-image content type should return 400."""
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(content_type="application/pdf", filename="face.pdf"),
            "body_photo": _fake_image(),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 400
    assert "face_photo" in resp.json()["detail"]


async def test_generation_both_photos_invalid_type(client: httpx.AsyncClient):
    """When face_photo has an invalid type, error mentions face_photo (first validated)."""
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(content_type="text/plain", filename="face.txt"),
            "body_photo": _fake_image(content_type="text/plain", filename="body.txt"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "content_type",
    ["image/jpeg", "image/png", "image/webp"],
    ids=["jpeg", "png", "webp"],
)
async def test_generation_accepted_image_types(
    client: httpx.AsyncClient,
    content_type: str,
):
    """All three allowed image types should be accepted."""
    ext = content_type.split("/")[1]
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(content_type=content_type, filename=f"face.{ext}"),
            "body_photo": _fake_image(content_type=content_type, filename=f"body.{ext}"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 202


# =============================================================================
# 4. Authentication requirements
# =============================================================================


async def test_generation_requires_auth(client: httpx.AsyncClient):
    """Request without Authorization header should return 401."""
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
    )
    assert resp.status_code == 401


async def test_generation_invalid_token(client: httpx.AsyncClient):
    """Request with invalid JWT should return 401."""
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401


async def test_generation_nonexistent_user_token(client: httpx.AsyncClient):
    """Valid JWT for a user that doesn't exist should return 401."""
    ghost_id = uuid.uuid4()
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(ghost_id),
    )
    assert resp.status_code == 401


# =============================================================================
# 5. Storage failure → 502
# =============================================================================


async def test_generation_storage_failure_returns_502(
    failing_client: httpx.AsyncClient,
):
    """When MinIO is down, the endpoint should return 502 Bad Gateway."""
    resp = await failing_client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 502
    assert "Failed to store" in resp.json()["detail"]


# =============================================================================
# 6. Response structure
# =============================================================================


async def test_generation_response_structure(client: httpx.AsyncClient):
    """Verify 202 response matches the GenerationAcceptedResponse schema."""
    resp = await client.post(
        "/api/v1/generations",
        data=VALID_FORM,
        files={
            "face_photo": _fake_image(),
            "body_photo": _fake_image(filename="body.jpg"),
        },
        headers=_auth_header(),
    )
    assert resp.status_code == 202
    body = resp.json()
    # All expected fields present
    assert set(body.keys()) == {"generation_id", "status", "message", "status_poll_url"}
    # generation_id is a valid UUID
    uuid.UUID(body["generation_id"])
    # status_poll_url contains the generation_id
    assert body["generation_id"] in body["status_poll_url"]
    assert body["status_poll_url"].startswith(settings.API_V1_PREFIX)


async def test_generation_unique_ids(client: httpx.AsyncClient):
    """Multiple generation requests should produce unique generation IDs."""
    ids = set()
    for _ in range(3):
        resp = await client.post(
            "/api/v1/generations",
            data=VALID_FORM,
            files={
                "face_photo": _fake_image(),
                "body_photo": _fake_image(filename="body.jpg"),
            },
            headers=_auth_header(),
        )
        assert resp.status_code == 202
        ids.add(resp.json()["generation_id"])
    assert len(ids) == 3, "Each generation must produce a unique ID"
