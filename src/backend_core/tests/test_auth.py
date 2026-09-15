from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import AsyncGenerator, Dict, Optional
import uuid

import httpx
from jose import jwt
import pytest

# Ensure backend_core directory is on sys.path regardless of where pytest is run
backend_core_dir = Path(__file__).resolve().parent.parent
if str(backend_core_dir) not in sys.path:
    sys.path.insert(0, str(backend_core_dir))

from app.core.config import settings
from app.core.dependencies import get_user_repository
from app.db.repositories.user_repository import UserRepository
from app.main import app
from app.models.user import User


class InMemoryUserRepository(UserRepository):
    """In-memory mock repository for isolated API testing."""

    def __init__(self) -> None:
        self.users: Dict[uuid.UUID, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        clean_email = email.strip().lower()
        for user in self.users.values():
            if user.email == clean_email:
                return user
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


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    """Provide a fresh in-memory repository for each test."""
    return InMemoryUserRepository()


@pytest.fixture
async def client(user_repo: InMemoryUserRepository) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an HTTP test client with overridden database dependency."""
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =============================================================================
# 1. Registration Success & Boundary Tests (POST /api/v1/auth/register)
# =============================================================================

@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"name": "Anna", "email": "anna@example.com", "password": "SecurePassword123!"}, id="standard"),
        pytest.param({"name": "Jean-Luc O'Connor", "email": "jean-luc.oconnor@domain.co.uk", "password": "ComplexPassword!99"}, id="symbols_in_name"),
        pytest.param({"name": "Алексей Смирнов", "email": "alexey.smirnov@yandex.ru", "password": "ПарольНаКириллице123!"}, id="cyrillic"),
        pytest.param({"name": "Plus User", "email": "user+style10@stylist.ai", "password": "MyStrongPassword2026"}, id="email_plus"),
        pytest.param({"name": "Min Password", "email": "minpass@domain.com", "password": "12345678"}, id="pass_8_chars"),
        pytest.param({"name": "Max Password", "email": "maxpass@domain.com", "password": "Abcd" * 18}, id="pass_72_chars"),
    ],
)
async def test_register_success(client: httpx.AsyncClient, payload: dict) -> None:
    """Test successful registration and token creation (HTTP 201 Created)."""
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "id" in data
    assert uuid.UUID(data["id"])


# =============================================================================
# 2. Registration Validation & Attack Rejections (POST /api/v1/auth/register)
# =============================================================================

@pytest.mark.parametrize(
    "invalid_payload",
    [
        pytest.param({"name": "", "email": "test@example.com", "password": "SecurePassword123!"}, id="empty_name"),
        pytest.param({"name": "   ", "email": "test@example.com", "password": "SecurePassword123!"}, id="space_name"),
        pytest.param({"name": "A" * 101, "email": "test@example.com", "password": "SecurePassword123!"}, id="long_name"),
        pytest.param({"name": "Anna", "email": "not-an-email", "password": "SecurePassword123!"}, id="bad_email"),
        pytest.param({"name": "Anna", "email": "user@", "password": "SecurePassword123!"}, id="no_domain"),
        pytest.param({"name": "Anna", "email": "@domain.com", "password": "SecurePassword123!"}, id="no_user"),
        pytest.param({"name": "Anna", "email": "user @domain.com", "password": "SecurePassword123!"}, id="space_in_email"),
        pytest.param({"name": "Anna", "email": "dots@example.com", "password": "............"}, id="dots_pass"), 
        pytest.param({"name": "Anna", "email": "test@example.com", "password": "short12"}, id="short_pass"),
        pytest.param({"name": "Anna", "email": "test@example.com", "password": "        "}, id="space_pass"),
        pytest.param({"name": "Anna", "email": "test@example.com", "password": "Abcd" * 18 + "e"}, id="long_pass"),
        pytest.param({"name": "Anna", "email": "test@example.com", "password": "h * 20"}, id="unique_char_pass"),
    ],
)
async def test_register_validation_errors(client: httpx.AsyncClient, invalid_payload: dict) -> None:
    """Test registration input validation rejection (HTTP 400 Bad Request)."""
    response = await client.post("/api/v1/auth/register", json=invalid_payload)
    assert response.status_code == 400


# =============================================================================
# 3. Registration Duplication & Normalization (POST /api/v1/auth/register)
# =============================================================================

@pytest.mark.parametrize(
    "first_email, second_email",
    [
        pytest.param("duplicate@example.com", "duplicate@example.com", id="exact"),
        pytest.param("case@example.com", "CASE@EXAMPLE.COM", id="case_diff"),
        pytest.param("spaces@example.com", "  spaces@example.com  ", id="spaces"),
        pytest.param("mixed.case@test.io", "  MIXED.CASE@TEST.IO  ", id="case_and_spaces"),
    ],
)
async def test_register_duplicate_email(
    client: httpx.AsyncClient, first_email: str, second_email: str
) -> None:
    """Test duplicate registration rejection (HTTP 409 Conflict)."""
    payload1 = {"name": "User One", "email": first_email, "password": "SecurePassword123!"}
    payload2 = {"name": "User Two", "email": second_email, "password": "SecurePassword123!"}

    res1 = await client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409


# =============================================================================
# 4. Login Success & Normalization (POST /api/v1/auth/login)
# =============================================================================

@pytest.mark.parametrize(
    "reg_email, login_email, password",
    [
        pytest.param("anna@example.com", "anna@example.com", "SecurePassword123!", id="standard"),
        pytest.param("case.user@service.net", "CASE.USER@SERVICE.NET", "SuperP@ssw0rd!", id="upper_email"),
        pytest.param("unicode@test.ru", "unicode@test.ru", "РусскийПароль2026!", id="cyrillic"),
        pytest.param("long@test.com", "long@test.com", "Abcd" * 18, id="pass_72_chars"),
    ],
)
async def test_login_success(
    client: httpx.AsyncClient, reg_email: str, login_email: str, password: str
) -> None:
    """Test successful login and JWT issuance (HTTP 200 OK)."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": reg_email, "password": password},
    )
    user_id = reg_res.json()["id"]

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": login_email, "password": password},
    )
    assert login_res.status_code == 200

    data = login_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["id"] == user_id


# =============================================================================
# 5. Login Failure Cases & Injection Attacks (POST /api/v1/auth/login)
# =============================================================================

@pytest.mark.parametrize(
    "email, password",
    [
        pytest.param("nonexistent@example.com", "SecurePassword123!", id="no_user"),
        pytest.param("registered@example.com", "WrongPassword!", id="bad_pass"),
        pytest.param("registered@example.com", "SecurePassword123! ", id="trailing_space"),
        pytest.param("registered@example.com", "short", id="short_pass"),
        pytest.param("registered@example.com", "' OR '1'='1", id="sql_injection"),
    ],
)
async def test_login_invalid_credentials(
    client: httpx.AsyncClient, email: str, password: str
) -> None:
    """Test login rejection with invalid credentials or injection (HTTP 401 Unauthorized)."""
    # Pre-register a valid account
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Valid User", "email": "registered@example.com", "password": "SecurePassword123!"},
    )

    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 401


# =============================================================================
# 6. Deactivated Account Handling (Login & Token Verification)
# =============================================================================

async def test_deactivated_user_cannot_login(
    client: httpx.AsyncClient, user_repo: InMemoryUserRepository
) -> None:
    """Test that deactivated users cannot log in even with correct password."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Blocked", "email": "blocked@example.com", "password": "Password123!"},
    )
    user_id = uuid.UUID(reg_res.json()["id"])

    # Deactivate account in repository
    user = await user_repo.get_by_id(user_id)
    assert user is not None
    user.is_active = False

    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "blocked@example.com", "password": "Password123!"},
    )
    assert res.status_code == 401


async def test_deactivated_user_token_rejected_on_me(
    client: httpx.AsyncClient, user_repo: InMemoryUserRepository
) -> None:
    """Test that token for an account that was deactivated is rejected on /me."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Deactivated", "email": "deactivated@example.com", "password": "Password123!"},
    )
    token = reg_res.json()["access_token"]
    user_id = uuid.UUID(reg_res.json()["id"])

    # Deactivate account in repository
    user = await user_repo.get_by_id(user_id)
    assert user is not None
    user.is_active = False

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


# =============================================================================
# 7. Current User Profile Tests (GET /api/v1/auth/me)
# =============================================================================

@pytest.mark.parametrize(
    "name, email, password",
    [
        pytest.param("Anna", "anna@example.com", "SecurePassword123!", id="standard"),
        pytest.param("Иван Сидоров", "ivan.sidorov@mail.ru", "MySecretPassword123", id="cyrillic"),
    ],
)
async def test_get_me_success(
    client: httpx.AsyncClient, name: str, email: str, password: str
) -> None:
    """Test retrieving authenticated user profile data (HTTP 200 OK)."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    token = reg_res.json()["access_token"]
    user_id = reg_res.json()["id"]

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == user_id
    assert data["email"] == email.strip().lower()
    assert data["name"] == name.strip()
    assert data["is_active"] is True
    assert "created_at" in data


async def test_get_me_token_idempotency(client: httpx.AsyncClient) -> None:
    """Test that the same JWT token can be safely reused multiple times without state changes."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Repeater", "email": "repeat@example.com", "password": "Password123!"},
    )
    token = reg_res.json()["access_token"]

    for _ in range(3):
        res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200


# =============================================================================
# 8. JWT Security & Attack Scenarios (GET /api/v1/auth/me)
# =============================================================================

@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="missing"),
        pytest.param({"Authorization": ""}, id="empty_val"),
        pytest.param({"Authorization": "Bearer "}, id="empty_token"),
        pytest.param({"Authorization": "Bearer not-a-jwt"}, id="bad_token"),
        pytest.param({"Authorization": "Bearer header.payload.signature"}, id="fake_jwt"),
        pytest.param({"Authorization": "Basic dXNlcjpwYXNz"}, id="basic_auth"),
        pytest.param({"Authorization": "Token some-token"}, id="custom_token"),
    ],
)
async def test_get_me_malformed_headers(client: httpx.AsyncClient, headers: dict) -> None:
    """Test rejection of malformed or unsupported authorization headers (HTTP 401 Unauthorized)."""
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401


async def test_get_me_forged_signature_token(client: httpx.AsyncClient) -> None:
    """Test that a token signed with an attacker's wrong secret key is rejected (HTTP 401)."""
    fake_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "attacker-compromised-secret-key",
        algorithm=settings.ALGORITHM,
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fake_token}"})
    assert res.status_code == 401


async def test_get_me_expired_token(client: httpx.AsyncClient) -> None:
    """Test that an expired JWT token is rejected (HTTP 401 Unauthorized)."""
    expired_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) - timedelta(minutes=10)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401


async def test_get_me_non_uuid_subject_token(client: httpx.AsyncClient) -> None:
    """Test that a token with non-UUID subject payload is safely rejected (HTTP 401)."""
    invalid_sub_token = jwt.encode(
        {"sub": "admin_username_not_uuid", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {invalid_sub_token}"})
    assert res.status_code == 401


async def test_get_me_deleted_user_token(client: httpx.AsyncClient) -> None:
    """Test that a valid token for a user that no longer exists in DB returns HTTP 401."""
    nonexistent_user_id = uuid.uuid4()
    ghost_token = jwt.encode(
        {"sub": str(nonexistent_user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})
    assert res.status_code == 401
