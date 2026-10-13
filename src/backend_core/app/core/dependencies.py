import uuid
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.repositories.album_repository import AlbumRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import get_db
from app.models.user import User
from app.services.album_service import AlbumService
from app.services.auth_service import AuthService
from app.services.generation_service import GenerationService
from app.services.storage_service import StorageService

http_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Singletons — created once per process lifetime
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    """Singleton provider for StorageService (MinIO).

    Using lru_cache ensures only one instance (and one pair of MinIO clients)
    is created for the entire process lifetime, enabling connection reuse.
    """
    return StorageService()


# AICoreClient is imported lazily to avoid circular imports at module load time
@lru_cache(maxsize=1)
def _create_ai_core_client():
    from app.services.ai_core_client import AICoreClient
    return AICoreClient()


def get_ai_core_client():
    """Singleton provider for AICoreClient.

    Returns the same AICoreClient instance for every request, so the
    underlying httpx connection pool is shared and reused.
    """
    return _create_ai_core_client()


# ---------------------------------------------------------------------------
# Per-request dependencies (DB session-scoped)
# ---------------------------------------------------------------------------

def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    """Dependency provider for UserRepository."""
    return UserRepository(session=session)


def get_album_repository(session: AsyncSession = Depends(get_db)) -> AlbumRepository:
    """Dependency provider for AlbumRepository."""
    return AlbumRepository(session=session)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(user_repo=user_repo)


def get_generation_service(
    album_repo: AlbumRepository = Depends(get_album_repository),
    storage: StorageService = Depends(get_storage_service),
) -> GenerationService:
    """Dependency provider for GenerationService."""
    from app.services.ai_core_client import AICoreClient
    return GenerationService(
        album_repo=album_repo,
        storage=storage,
        ai_client=get_ai_core_client(),
    )


def get_album_service(
    album_repo: AlbumRepository = Depends(get_album_repository),
    storage: StorageService = Depends(get_storage_service),
) -> AlbumService:
    """Dependency provider for AlbumService."""
    return AlbumService(album_repo=album_repo, storage=storage)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    """Dependency to retrieve and validate the current authenticated user from JWT."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub: Optional[str] = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
