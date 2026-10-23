"""Read-only FastAdmin tables. Secrets are excluded from serialization."""
import uuid
from datetime import datetime, timezone
from fastadmin import SqlAlchemyModelAdmin, register, display
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.album import Album
from app.models.user import User
from app.models.photo import Photo
from app.models.base import Base
from app.core.security import verify_password


class GenerationRecord(Base):
    __table__ = Album.__table__


class ReadOnlyAdmin(SqlAlchemyModelAdmin):
    list_per_page = 25
    ordering = ("-created_at",)

    async def has_add_permission(self, user_id=None): return False
    async def has_change_permission(self, user_id=None): return False
    async def has_delete_permission(self, user_id=None): return False
    async def has_export_permission(self, user_id=None): return False
    async def has_action_permission(self, user_id=None): return False


@register(User, sqlalchemy_sessionmaker=AsyncSessionLocal)
class UserAdmin(ReadOnlyAdmin):
    verbose_name = "Пользователь"
    verbose_name_plural = "Пользователи"
    fields = ("id", "name", "email", "is_active", "created_at")
    list_display = fields + ("details_url",)
    readonly_fields = fields
    exclude = ("password_hash", "is_admin", "albums")
    search_fields = ("name", "email", "id")
    list_display_labels = {"id": "ID", "name": "Имя", "email": "Email", "is_active": "Активен", "created_at": "Зарегистрирован", "details_url": "Карточка пользователя"}
    list_filter = ("is_active", "created_at")

    @display
    def details_url(self, obj): return f"/admin/user/{obj.id}"

    async def authenticate(self, username, password):
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.email == username.strip().lower(), User.is_admin.is_(True), User.is_active.is_(True)))
            if user and await verify_password(password, user.password_hash): return user.id
        return None


@register(GenerationRecord, sqlalchemy_sessionmaker=AsyncSessionLocal)
class GenerationAdmin(ReadOnlyAdmin):
    verbose_name = "Генерация"
    verbose_name_plural = "Генерации"
    fields = ("id", "generation_id", "ai_job_id", "status", "created_at", "finished_at", "updated_at",
              "situation", "styles", "shoes", "impressions", "total_photos", "next_retry_at",
              "results_ack_pending", "results_ack_next_attempt_at", "results_ack_error", "duration_seconds", "details_url")
    readonly_fields = fields
    list_display = ("generation_id", "ai_job_id", "status", "created_at", "duration_seconds", "updated_at", "details_url")
    search_fields = ("generation_id", "ai_job_id")
    list_filter = ("status", "created_at")

    @display
    def duration_seconds(self, obj):
        if obj.finished_at is None and obj.status in ("COMPLETED", "FAILED"): return None
        return max(0, int(((obj.finished_at or datetime.now(timezone.utc)) - obj.created_at).total_seconds()))

    @display
    def details_url(self, obj): return f"/admin/task/{obj.id}"


@register(Album, sqlalchemy_sessionmaker=AsyncSessionLocal)
class AlbumAdmin(ReadOnlyAdmin):
    verbose_name = "Альбом"
    verbose_name_plural = "Альбомы"
    list_display_labels = {"id": "ID", "title": "Название", "status": "Статус", "created_at": "Создан", "saved_photos": "Сохранено фото", "details_url": "Карточка генерации"}
    fields = ("id", "title", "user", "generation_id", "status", "created_at", "saved_photos", "is_archived", "details_url")
    readonly_fields = fields
    list_display = ("id", "title", "status", "created_at", "saved_photos", "details_url")
    search_fields = ("id", "title", "generation_id")
    list_filter = ("status", "created_at")
    exclude = ("dispatch_request", "pending_callback", "source_face_key", "source_body_key", "processing_token")

    @display
    def details_url(self, obj): return f"/admin/task/{obj.id}"


    @display
    async def saved_photos(self, obj):
        async with self.get_sessionmaker()() as session:
            return await session.scalar(select(func.count()).select_from(Photo).where(Photo.album_id == obj.id))
