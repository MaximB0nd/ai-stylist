"""Replace user_weight with gender in albums table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29 22:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old user_weight column and add gender VARCHAR(1)
    op.drop_column('albums', 'user_weight')
    op.add_column('albums', sa.Column('gender', sa.String(length=1), nullable=True))


def downgrade() -> None:
    op.drop_column('albums', 'gender')
    op.add_column('albums', sa.Column('user_weight', sa.SmallInteger(), nullable=True))
