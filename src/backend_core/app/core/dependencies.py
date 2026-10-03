import uuid
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


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    """Dependency provider for UserRepository."""
    return UserRepository(session=session)


def get_album_repository(session: AsyncSession = Depends(get_db)) -> AlbumRepository:
    """Dependency provider for AlbumRepository."""
    return AlbumRepository(session=session)


def get_storage_service() -> StorageService:
    """Dependency provider for StorageService (MinIO)."""
    return StorageService()


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(user_repo=user_repo)


from app.services.ai_core_client import AICoreClient


def get_ai_core_client() -> AICoreClient:
    """Dependency provider for AICoreClient."""
    return AICoreClient()


def get_generation_service(
    album_repo: AlbumRepository = Depends(get_album_repository),
    storage: StorageService = Depends(get_storage_service),
    ai_client: AICoreClient = Depends(get_ai_core_client),
) -> GenerationService:
    """Dependency provider for GenerationService."""
    return GenerationService(album_repo=album_repo, storage=storage, ai_client=ai_client)


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
