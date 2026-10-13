"""Persist legacy completion callbacks before acknowledging delivery."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("albums", sa.Column("pending_callback", postgresql.JSONB()))

def downgrade():
    op.drop_column("albums", "pending_callback")
