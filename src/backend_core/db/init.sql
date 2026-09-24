BEGIN;

-- Enable pgcrypto for gen_random_uuid() (built-in in PG 16)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- Table: users
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email);

-- =============================================================================
-- Table: albums
-- =============================================================================
CREATE TABLE IF NOT EXISTS albums (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    generation_id UUID NOT NULL,
    title VARCHAR(100) NOT NULL,
    situation VARCHAR(50) NOT NULL,
    styles JSONB NOT NULL DEFAULT '[]'::jsonb,
    shoes JSONB NOT NULL DEFAULT '[]'::jsonb,
    impressions JSONB NOT NULL DEFAULT '[]'::jsonb,
    user_age SMALLINT NULL,
    user_height SMALLINT NULL,
    user_weight SMALLINT NULL,
    source_face_key VARCHAR(512) NULL,
    source_body_key VARCHAR(512) NULL,
    total_photos INTEGER NOT NULL DEFAULT 10,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_albums_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_albums_user_id ON albums(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_albums_generation_id ON albums(generation_id);
CREATE INDEX IF NOT EXISTS idx_albums_user_created ON albums(user_id, created_at);

-- =============================================================================
-- Table: photos
-- =============================================================================
CREATE TABLE IF NOT EXISTS photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    album_id UUID NOT NULL,
    order_index SMALLINT NOT NULL,
    object_key VARCHAR(512) NOT NULL,
    is_cover BOOLEAN NOT NULL DEFAULT FALSE,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_photos_album_id FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
    CONSTRAINT uq_photos_album_order UNIQUE (album_id, order_index),
    CONSTRAINT chk_photos_order_index CHECK (order_index >= 0 AND order_index < 10)
);

CREATE INDEX IF NOT EXISTS ix_photos_album_id ON photos(album_id);

-- =============================================================================
-- Table: alembic_version (Baseline stamp for Alembic migrations)
-- Stamped at the end of transaction after all schema elements are established.
-- =============================================================================
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INSERT INTO alembic_version (version_num) VALUES ('0001') ON CONFLICT DO NOTHING;

COMMIT;
