"""Persist delivery acknowledgements and dependency retry deadlines."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("albums", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("albums", sa.Column("results_ack_pending", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("albums", sa.Column("results_ack_next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("albums", sa.Column("results_ack_error", sa.String(512), nullable=True))


def downgrade():
    for name in ("results_ack_error", "results_ack_next_attempt_at", "results_ack_pending", "next_retry_at"):
        op.drop_column("albums", name)
