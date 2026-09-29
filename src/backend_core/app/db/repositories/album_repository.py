import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.album import Album
from app.models.photo import Photo


class AlbumRepository:
    """Repository handling database operations for Album and Photo entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_with_photos(self, album_id: uuid.UUID) -> Optional[Album]:
        """Fetch a single album with eagerly loaded photos, ordered by order_index."""
        stmt = (
            select(Album)
            .where(Album.id == album_id)
            .options(selectinload(Album.photos))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_album_ids(self, user_id: uuid.UUID) -> List[uuid.UUID]:
        """Fetch all album IDs belonging to a given user, ordered by creation date desc."""
        stmt = (
            select(Album.id)
            .where(Album.user_id == user_id)
            .order_by(Album.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_album(
        self,
        user_id: uuid.UUID,
        generation_id: uuid.UUID,
        title: str,
        situation: str,
        styles: list,
        shoes: list,
        impressions: list,
        user_age: Optional[int] = None,
        user_height: Optional[int] = None,
        gender: Optional[str] = None,
        source_face_key: Optional[str] = None,
        source_body_key: Optional[str] = None,
    ) -> Album:
        """Create and persist a new album record."""
        album = Album(
            user_id=user_id,
            generation_id=generation_id,
            title=title,
            situation=situation,
            styles=styles,
            shoes=shoes,
            impressions=impressions,
            user_age=user_age,
            user_height=user_height,
            gender=gender,
            source_face_key=source_face_key,
            source_body_key=source_body_key,
        )
        try:
            self.session.add(album)
            await self.session.commit()
            await self.session.refresh(album)
            return album
        except Exception:
            await self.session.rollback()
            raise
