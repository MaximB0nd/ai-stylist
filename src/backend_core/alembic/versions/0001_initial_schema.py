"""Initial schema for users, albums, and photos

Revision ID: 0001
Revises: None
Create Date: 2026-09-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'albums',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('generation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('situation', sa.String(length=50), nullable=False),
        sa.Column('styles', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('shoes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('impressions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('user_age', sa.SmallInteger(), nullable=True),
        sa.Column('user_height', sa.SmallInteger(), nullable=True),
        sa.Column('user_weight', sa.SmallInteger(), nullable=True),
        sa.Column('source_face_key', sa.String(length=512), nullable=True),
        sa.Column('source_body_key', sa.String(length=512), nullable=True),
        sa.Column('total_photos', sa.Integer(), server_default=sa.text('10'), nullable=False),
        sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_albums_user_created', 'albums', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_albums_generation_id', 'albums', ['generation_id'], unique=True)
    op.create_index('ix_albums_user_id', 'albums', ['user_id'], unique=False)

    op.create_table(
        'photos',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('album_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_index', sa.SmallInteger(), nullable=False),
        sa.Column('object_key', sa.String(length=512), nullable=False),
        sa.Column('is_cover', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_favorite', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('order_index >= 0 AND order_index < 10', name='chk_photos_order_index'),
        sa.ForeignKeyConstraint(['album_id'], ['albums.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('album_id', 'order_index', name='uq_photos_album_order')
    )
    op.create_index('ix_photos_album_id', 'photos', ['album_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_photos_album_id', table_name='photos')
    op.drop_table('photos')
    op.drop_index('ix_albums_user_id', table_name='albums')
    op.drop_index('ix_albums_generation_id', table_name='albums')
    op.drop_index('idx_albums_user_created', table_name='albums')
    op.drop_table('albums')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
