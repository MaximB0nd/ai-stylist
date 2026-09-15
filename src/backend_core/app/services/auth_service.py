from fastapi import HTTPException, status

from app.core.security import create_access_token, hash_password, verify_password
from app.db.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserLoginRequest, UserRegisterRequest


class AuthService:
    """Service encapsulating user registration and authentication business logic."""

    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def register(self, data: UserRegisterRequest) -> TokenResponse:
        """Register a new user, persist to database, and issue an access token."""
        existing_user = await self.user_repo.get_by_email(data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        password_hash = hash_password(data.password)
        user = await self.user_repo.create(
            name=data.name,
            email=data.email,
            password_hash=password_hash,
        )

        access_token = create_access_token(subject=user.id)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            id=user.id,
        )

    async def login(self, data: UserLoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue an access token."""
        user = await self.user_repo.get_by_email(data.email)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        access_token = create_access_token(subject=user.id)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            id=user.id,
        )
