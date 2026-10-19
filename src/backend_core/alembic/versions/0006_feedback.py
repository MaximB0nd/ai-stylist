"""Add authenticated user feedback."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 100", name="ck_feedback_name_length"),
        sa.CheckConstraint("char_length(email) BETWEEN 1 AND 254", name="ck_feedback_email_length"),
        sa.CheckConstraint("char_length(btrim(comment)) BETWEEN 1 AND 5000", name="ck_feedback_comment_length"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])


def downgrade():
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")
