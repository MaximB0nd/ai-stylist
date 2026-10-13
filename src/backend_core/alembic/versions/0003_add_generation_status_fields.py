"""Add generation status, ai_job_id and error_message to albums table

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'albums',
        sa.Column(
            'status',
            sa.String(length=20),
            server_default=sa.text("'VALIDATING'"),
            nullable=False,
        ),
    )
    op.add_column(
        'albums',
        sa.Column('ai_job_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'albums',
        sa.Column('error_message', sa.String(length=512), nullable=True),
    )
    op.create_index(op.f('ix_albums_status'), 'albums', ['status'], unique=False)
    op.create_index(op.f('ix_albums_ai_job_id'), 'albums', ['ai_job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_albums_ai_job_id'), table_name='albums')
    op.drop_index(op.f('ix_albums_status'), table_name='albums')
    op.drop_column('albums', 'error_message')
    op.drop_column('albums', 'ai_job_id')
    op.drop_column('albums', 'status')
