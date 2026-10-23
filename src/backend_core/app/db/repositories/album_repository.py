import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, case, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.album import Album
from app.models.photo import Photo
from app.core.config import settings


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

    async def get_user_album_ids(
        self,
        user_id: uuid.UUID,
        status: Optional[str] = "COMPLETED",
    ) -> List[uuid.UUID]:
        """Fetch album IDs belonging to a user, ordered by creation date desc.

        Filters by status='COMPLETED' by default so gallery lists only completed albums.
        Pass status=None to retrieve all albums regardless of status.
        """
        stmt = select(Album.id).where(Album.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Album.status == status)
        stmt = stmt.order_by(Album.created_at.desc())
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
        """Update album processing status, error message, and optional AI job ID."""
        album = await self.session.get(Album, album_id)
        if not album:
            return None
        if status in ("COMPLETED", "FAILED") and album.status not in ("COMPLETED", "FAILED") and album.finished_at is None:
            album.finished_at = datetime.now(timezone.utc)
        album.status = status
        # Explicitly set updated_at — SQLAlchemy Python-side onupdate is not
        # reliably triggered for AsyncSession attribute assignments.
        album.updated_at = datetime.now(timezone.utc)
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

    async def atomic_claim_for_download(
        self,
        album_id: uuid.UUID,
    ) -> Optional[uuid.UUID]:
        """Enter DOWNLOADING and return its ownership token, or None if busy/final."""
        return await self.claim_work(
            album_id, ["VALIDATING", "QUEUED", "PROCESSING", "DOWNLOADING"],
            to_status="DOWNLOADING",
        )

    async def claim_work(self, album_id, from_statuses, to_status=None) -> Optional[uuid.UUID]:
        """Acquire a renewable lease; an expired worker cannot commit results."""
        now = datetime.now(timezone.utc)
        token = uuid.uuid4()
        values = dict(
            processing_token=token,
            lease_expires_at=now + timedelta(seconds=settings.GENERATION_LEASE_SECONDS),
            updated_at=now,
        )
        if to_status is not None:
            values["status"] = to_status
        stmt = (
            update(Album)
            .where(
                Album.id == album_id,
                Album.status.in_(from_statuses),
                or_(Album.processing_token.is_(None), Album.lease_expires_at <= now),
            )
            .values(**values)
            .returning(Album.id)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return token if result.scalar_one_or_none() is not None else None

    async def renew_lease(self, album_id, token) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(Album).where(
                Album.id == album_id, Album.processing_token == token,
                Album.lease_expires_at > now,
                Album.status.not_in(["COMPLETED", "FAILED"]),
            ).values(lease_expires_at=now + timedelta(seconds=settings.GENERATION_LEASE_SECONDS))
            .returning(Album.id)
        )
        await self.session.commit()
        return result.scalar_one_or_none() is not None

    async def finish_work(self, album_id, token, release=True, **values) -> bool:
        """Apply progress/error only while this worker owns the live lease."""
        now = datetime.now(timezone.utc)
        if values.get("status") in ("COMPLETED", "FAILED"):
            values["finished_at"] = func.coalesce(Album.finished_at, now)
        if release:
            values.update(processing_token=None, lease_expires_at=None)
        result = await self.session.execute(
            update(Album).where(
                Album.id == album_id, Album.processing_token == token,
                Album.lease_expires_at > now,
                Album.status.not_in(["COMPLETED", "FAILED"]),
            ).values(**values, updated_at=now)
            .returning(Album.id)
        )
        await self.session.commit()
        return result.scalar_one_or_none() is not None

    async def save_dispatch_request(self, album_id, token, request) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(Album).where(
                Album.id == album_id, Album.processing_token == token,
                Album.lease_expires_at > now, Album.status == "VALIDATING",
            ).values(dispatch_request=request).returning(Album.id)
        )
        await self.session.commit()
        return result.scalar_one_or_none() is not None

    async def record_dispatch(self, album_id, token, ai_job_id, status) -> bool:
        """Attach the remote ID without regressing an early progress webhook."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(Album).where(
                Album.id == album_id, Album.processing_token == token,
                Album.lease_expires_at > now, Album.status.not_in(["COMPLETED", "FAILED"]),
            ).values(
                finished_at=case((Album.status == "VALIDATING", func.coalesce(Album.finished_at, now)), else_=Album.finished_at) if status == "FAILED" else Album.finished_at,
                ai_job_id=ai_job_id,
                status=case((Album.status == "VALIDATING", status), else_=Album.status),
                processing_token=None, lease_expires_at=None, updated_at=now, error_message=None, next_retry_at=None,
            ).returning(Album.id)
        )
        await self.session.commit()
        return result.scalar_one_or_none() is not None

    async def get_recoverable_albums(self) -> List[Album]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Album).where(
                Album.status.in_(["VALIDATING", "QUEUED", "PROCESSING", "DOWNLOADING"]),
                Album.updated_at < now - timedelta(seconds=settings.GENERATION_RECOVERY_INTERVAL_SECONDS),
                or_(Album.next_retry_at.is_(None), Album.next_retry_at <= now,
                    Album.created_at <= now - timedelta(seconds=settings.GENERATION_TIMEOUT_SECONDS)),
                or_(Album.processing_token.is_(None), Album.lease_expires_at <= now),
            ).order_by(Album.updated_at).limit(100)
        )
        return list(result.scalars().all())

    async def complete_with_photos(self, album_id, photos_data, token, *, ack_job_id=None) -> bool:
        """Commit the photo replacement and final state in one fenced transaction."""
        try:
            now = datetime.now(timezone.utc)
            result = await self.session.execute(
                update(Album).where(
                    Album.id == album_id, Album.status == "DOWNLOADING",
                    Album.processing_token == token, Album.lease_expires_at > now,
                ).values(status="COMPLETED", finished_at=func.coalesce(Album.finished_at, now), total_photos=len(photos_data), error_message=None,
                         processing_token=None, lease_expires_at=None, pending_callback=None, updated_at=now,
                         next_retry_at=None, results_ack_pending=ack_job_id is not None,
                         results_ack_next_attempt_at=now if ack_job_id is not None else None,
                         results_ack_error=None,
                         **({"ai_job_id": ack_job_id} if ack_job_id is not None else {}))
                .returning(Album.id)
            )
            if result.scalar_one_or_none() is None:
                await self.session.rollback()
                return False
            await self.session.execute(delete(Photo).where(Photo.album_id == album_id))
            self.session.add_all([Photo(album_id=album_id, **item) for item in photos_data])
            await self.session.commit()
            return True
        except Exception:
            await self.session.rollback()
            raise

    async def persist_callback(self, album_id, photos_data):
        """Serialize competing callbacks; acknowledge only after durable storage."""
        result = await self.session.execute(select(Album).where(Album.id == album_id).with_for_update().execution_options(populate_existing=True))
        album = result.scalar_one()
        if album.status in ("COMPLETED", "FAILED"):
            await self.session.commit()
            return "already_finalized"
        if album.pending_callback is not None and album.pending_callback != photos_data:
            await self.session.rollback()
            raise ValueError("Conflicting completion callback")
        album.pending_callback = photos_data
        await self.session.commit()
        return "accepted"

    async def delete_orphan_attempt(self, album_id, token, prefix, storage):
        """Lock the album against completion while proving its attempt is unreferenced."""
        import asyncio
        result = await self.session.execute(select(Album).where(Album.id == album_id).with_for_update().execution_options(populate_existing=True))
        album = result.scalar_one_or_none()
        if album and album.processing_token == token and album.lease_expires_at and album.lease_expires_at > datetime.now(timezone.utc):
            await self.session.rollback()
            return
        references = await self.session.execute(select(Photo.id).where(Photo.object_key.startswith(prefix)).limit(1))
        pending = (album.pending_callback or []) if album else []
        if references.scalar_one_or_none() is None and not any(p["object_key"].startswith(prefix) for p in pending):
            await asyncio.to_thread(storage.delete_attempt, prefix)
        await self.session.rollback()

    async def atomic_transition(
        self,
        album_id: uuid.UUID,
        from_statuses: List[str],
        to_status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Atomically transition album status ONLY if current status is in from_statuses.

        Prevents delayed/out-of-order events from regressing advanced states
        (e.g., delayed PROCESSING event overwriting DOWNLOADING or COMPLETED).
        """
        now = datetime.now(timezone.utc)
        values = {"status": to_status, "updated_at": now}
        if to_status in ("COMPLETED", "FAILED"):
            values["finished_at"] = case((Album.status.not_in(["COMPLETED", "FAILED"]), func.coalesce(Album.finished_at, now)), else_=Album.finished_at)
        if error_message is not None:
            values["error_message"] = error_message

        stmt = (
            update(Album)
            .where(
                Album.id == album_id,
                Album.status.in_(from_statuses),
            )
            .values(**values)
            .returning(Album.id)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none() is not None

    async def get_stuck_downloading_albums(
        self, stale_seconds: int = 0
    ) -> List[Album]:
        """Fetch albums stuck in DOWNLOADING status (e.g., across server restarts)."""
        stmt = select(Album).where(Album.status == "DOWNLOADING")
        if stale_seconds > 0:
            now = datetime.now(timezone.utc)
            threshold = now - timedelta(seconds=stale_seconds)
            stmt = stmt.where(Album.updated_at < threshold)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_photos(
        self,
        album_id: uuid.UUID,
        photos_data: List[dict],
    ) -> List[Photo]:
        """Batch insert photos for an album idempotently.

        Deletes any pre-existing photos for this album within the same transaction
        before inserting, preventing UniqueConstraint collisions on download retry.
        """
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
            await self.session.execute(
                delete(Photo).where(Photo.album_id == album_id)
            )
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
            finished_at=datetime.now(timezone.utc) if status in ("COMPLETED", "FAILED") else None,
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


    async def get_pending_result_acks(self):
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Album.id, Album.ai_job_id).where(
                Album.status == "COMPLETED", Album.results_ack_pending.is_(True),
                or_(Album.results_ack_next_attempt_at.is_(None), Album.results_ack_next_attempt_at <= now),
            ).order_by(Album.results_ack_next_attempt_at).limit(100)
        )
        return list(result.all())

    async def record_result_ack(self, album_id, job_id, *, pending, next_attempt_at=None, error=None):
        await self.session.execute(
            update(Album).where(
                Album.id == album_id, Album.ai_job_id == job_id,
                Album.status == "COMPLETED", Album.results_ack_pending.is_(True),
            ).values(results_ack_pending=pending, results_ack_next_attempt_at=next_attempt_at,
                     results_ack_error=error)
        )
        await self.session.commit()
