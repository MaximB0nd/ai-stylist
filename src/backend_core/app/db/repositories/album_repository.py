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

    async def get_by_generation_id(self, generation_id: uuid.UUID) -> Optional[Album]:
        """Fetch a single album by generation_id with eagerly loaded photos."""
        stmt = (
            select(Album)
            .where(Album.generation_id == generation_id)
            .options(selectinload(Album.photos))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ai_job_id(self, ai_job_id: uuid.UUID) -> Optional[Album]:
        """Fetch album by AI Core job ID with photos preloaded."""
        stmt = (
            select(Album)
            .where(Album.ai_job_id == ai_job_id)
            .options(selectinload(Album.photos))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


    async def update_status(
        self,
        album_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None,
        ai_job_id: Optional[uuid.UUID] = None,
    ) -> Optional[Album]:
        """Update album processing status and optional error/job_id."""
        album = await self.session.get(Album, album_id)
        if not album:
            return None
        album.status = status
        if error_message is not None:
            album.error_message = error_message
        if ai_job_id is not None:
            album.ai_job_id = ai_job_id
        try:
            await self.session.commit()
            await self.session.refresh(album)
            return album
        except Exception:
            await self.session.rollback()
            raise

    async def add_photos(
        self,
        album_id: uuid.UUID,
        photos_data: List[dict],
    ) -> List[Photo]:
        """Batch insert photos for an album."""
        created_photos = [
            Photo(
                album_id=album_id,
                order_index=item["order_index"],
                object_key=item["object_key"],
                is_cover=item.get("is_cover", False),
                is_favorite=item.get("is_favorite", False),
            )
            for item in photos_data
        ]
        try:
            self.session.add_all(created_photos)
            await self.session.commit()
            for photo in created_photos:
                await self.session.refresh(photo)
            return created_photos
        except Exception:
            await self.session.rollback()
            raise

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
        status: str = "VALIDATING",
        ai_job_id: Optional[uuid.UUID] = None,
        error_message: Optional[str] = None,
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
            status=status,
            ai_job_id=ai_job_id,
            error_message=error_message,
        )
        try:
            self.session.add(album)
            await self.session.commit()
            await self.session.refresh(album)
            return album
        except Exception:
            await self.session.rollback()
            raise
