"""Persist generation leases and the original dispatch request."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("albums", sa.Column("processing_token", postgresql.UUID(as_uuid=True)))
    op.add_column("albums", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("albums", sa.Column("dispatch_request", postgresql.JSONB()))


def downgrade() -> None:
    op.drop_column("albums", "dispatch_request")
    op.drop_column("albums", "lease_expires_at")
    op.drop_column("albums", "processing_token")
