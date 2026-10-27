"""Bounded administrative reads; existing domain models remain authoritative."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from app.models.album import Album
from app.models.user import User


class AdminRepository:
    def __init__(self, session):
        self.session = session

    async def overview(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        counts = dict((await self.session.execute(select(Album.status, func.count()).group_by(Album.status))).all())
        recent = dict((await self.session.execute(select(Album.status, func.count()).where(
            Album.finished_at >= cutoff).group_by(Album.status))).all())
        oldest = await self.session.scalar(select(Album).where(
            Album.status.not_in(["COMPLETED", "FAILED"])).order_by(Album.created_at).limit(1))
        errors = list((await self.session.scalars(select(Album).where(
            Album.error_message.is_not(None)).order_by(Album.updated_at.desc()).limit(10))).all())
        return {"counts": counts, "recent": recent, "oldest": oldest, "errors": errors}

    async def task(self, album_id):
        return await self.session.get(Album, album_id)

    async def is_admin(self, user_id):
        return bool(await self.session.scalar(select(User.id).where(User.id == user_id, User.is_active.is_(True), User.is_admin.is_(True))))


    async def generations(self, status=None, search=None, offset=0, since=None, until=None):
        from sqlalchemy import or_
        query = select(Album)
        if status: query = query.where(Album.status == status)
        if since: query = query.where(Album.created_at >= since)
        if until: query = query.where(Album.created_at < until)
        if search:
            # Exact UUID search avoids wildcard expansion over potentially large tables.
            import uuid
            try: identifier = uuid.UUID(search)
            except ValueError: return [], 0
            query = query.where(or_(Album.generation_id == identifier, Album.ai_job_id == identifier))
        count = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = list((await self.session.scalars(query.order_by(Album.created_at.desc()).offset(offset).limit(25))).all())
        return rows, count


    async def user_details(self, user_id):
        user = await self.session.get(User, user_id)
        if user is None: return None
        tasks = list((await self.session.scalars(select(Album).where(Album.user_id == user_id).order_by(Album.created_at.desc()).limit(25))).all())
        return {"id": user.id, "name": user.name, "email": user.email, "is_active": user.is_active, "created_at": user.created_at}, tasks
