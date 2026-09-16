import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository handling database operations for the User entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a single user by primary key ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Fetch a single user by their unique email address."""
        stmt = select(User).where(User.email == email.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, name: str, email: str, password_hash: str) -> User:
        """Create and persist a new user record."""
        user = User(
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            is_active=True,
        )
        try:
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            return user
        except Exception:
            await self.session.rollback()
            raise
