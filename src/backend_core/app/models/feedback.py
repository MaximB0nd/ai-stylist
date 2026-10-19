"""Persist user-linked feedback and the contact details submitted with it."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 100", name="ck_feedback_name_length"),
        CheckConstraint("char_length(email) BETWEEN 1 AND 254", name="ck_feedback_email_length"),
        CheckConstraint("char_length(btrim(comment)) BETWEEN 1 AND 5000", name="ck_feedback_comment_length"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
