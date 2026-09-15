import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.photo import Photo
    from app.models.user import User


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    situation: Mapped[str] = mapped_column(String(50), nullable=False)
    styles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    shoes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    impressions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    user_age: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    user_height: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    user_weight: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    source_face_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_body_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    total_photos: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="albums")
    photos: Mapped[List["Photo"]] = relationship(
        "Photo", back_populates="album", cascade="all, delete-orphan", order_by="Photo.order_index"
    )

    __table_args__ = (
        Index("idx_albums_user_created", "user_id", "created_at"),
    )
