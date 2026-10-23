"""Add administrator role and trustworthy generation completion time."""
from alembic import op
import sqlalchemy as sa
revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("albums", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_albums_finished_at", "albums", ["finished_at"])


def downgrade():
    op.drop_index("ix_albums_finished_at", table_name="albums")
    op.drop_column("albums", "finished_at")
    op.drop_column("users", "is_admin")
