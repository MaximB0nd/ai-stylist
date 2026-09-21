import asyncio
import logging
import sys
from typing import List, Optional, Set

from sqlalchemy import inspect, text
from sqlalchemy.engine import Inspector
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [db.baseline] %(message)s",
)
logger = logging.getLogger("db.baseline")

MAX_RETRIES = 10
RETRY_DELAY_SECONDS = 2

EXPECTED_TABLES: Set[str] = {"users", "albums", "photos"}

EXPECTED_COLUMNS = {
    "users": {
        "id",
        "email",
        "password_hash",
        "name",
        "is_active",
        "created_at",
        "updated_at",
    },
    "albums": {
        "id",
        "user_id",
        "generation_id",
        "title",
        "situation",
        "styles",
        "shoes",
        "impressions",
        "user_age",
        "user_height",
        "user_weight",
        "source_face_key",
        "source_body_key",
        "total_photos",
        "is_archived",
        "created_at",
        "updated_at",
    },
    "photos": {
        "id",
        "album_id",
        "order_index",
        "object_key",
        "is_cover",
        "is_favorite",
        "created_at",
        "updated_at",
    },
}


class IncompatibleSchemaError(RuntimeError):
    """Raised when existing database schema does not match the revision 0001 fingerprint."""

    pass


def validate_schema_fingerprint(
    inspector: Inspector, schema: Optional[str] = None
) -> List[str]:
    """Validate database schema against the full fingerprint of Alembic revision '0001'.

    Checks required tables, column definitions, primary keys, foreign keys,
    indexes, unique constraints, and check constraints.

    Returns:
        List of error descriptions if any discrepancies are found, empty list otherwise.
    """
    errors: List[str] = []

    all_tables = set(inspector.get_table_names(schema=schema))
    app_tables = all_tables - {"alembic_version"}

    # 1. Table presence and unexpected tables check
    missing_tables = EXPECTED_TABLES - app_tables
    extra_tables = app_tables - EXPECTED_TABLES
    if missing_tables:
        errors.append(f"Missing required table(s): {sorted(missing_tables)}")
    if extra_tables:
        errors.append(f"Unexpected table(s): {sorted(extra_tables)}")

    # Only inspect tables that are actually present
    inspectable_tables = EXPECTED_TABLES & app_tables

    # 2. Columns check
    for table in sorted(inspectable_tables):
        actual_cols = {
            col["name"] for col in inspector.get_columns(table, schema=schema)
        }
        missing_cols = EXPECTED_COLUMNS[table] - actual_cols
        extra_cols = actual_cols - EXPECTED_COLUMNS[table]
        if missing_cols:
            errors.append(f"Table '{table}' missing column(s): {sorted(missing_cols)}")
        if extra_cols:
            errors.append(
                f"Table '{table}' has unexpected column(s): {sorted(extra_cols)}"
            )

    # 3. Primary keys check
    for table in sorted(inspectable_tables):
        pk = inspector.get_pk_constraint(table, schema=schema)
        pk_cols = pk.get("constrained_columns") or []
        if pk_cols != ["id"]:
            errors.append(
                f"Table '{table}' invalid primary key: expected ['id'], got {pk_cols}"
            )

    # Helper functions for index & unique constraint inspection
    def has_unique_constraint_or_index(
        table: str, cols: List[str], expected_name: Optional[str] = None
    ) -> bool:
        indexes = inspector.get_indexes(table, schema=schema)
        for idx in indexes:
            if idx.get("unique"):
                if idx.get("column_names") == cols:
                    return True
                if expected_name and idx.get("name") == expected_name:
                    return True
        try:
            uqs = inspector.get_unique_constraints(table, schema=schema)
            for uq in uqs:
                if uq.get("column_names") == cols:
                    return True
                if expected_name and uq.get("name") == expected_name:
                    return True
        except Exception:
            pass
        return False

    def has_index(
        table: str, cols: List[str], expected_name: Optional[str] = None
    ) -> bool:
        indexes = inspector.get_indexes(table, schema=schema)
        for idx in indexes:
            if idx.get("column_names") == cols:
                return True
            if expected_name and idx.get("name") == expected_name:
                return True
        return False

    # 4. Foreign keys check
    if "albums" in inspectable_tables:
        fks = inspector.get_foreign_keys("albums", schema=schema)
        has_user_fk = any(
            fk.get("referred_table") == "users"
            and fk.get("constrained_columns") == ["user_id"]
            and fk.get("referred_columns") == ["id"]
            for fk in fks
        )
        if not has_user_fk:
            errors.append(
                "Table 'albums' missing foreign key on 'user_id' referencing 'users(id)'"
            )

    if "photos" in inspectable_tables:
        fks = inspector.get_foreign_keys("photos", schema=schema)
        has_album_fk = any(
            fk.get("referred_table") == "albums"
            and fk.get("constrained_columns") == ["album_id"]
            and fk.get("referred_columns") == ["id"]
            for fk in fks
        )
        if not has_album_fk:
            errors.append(
                "Table 'photos' missing foreign key on 'album_id' referencing 'albums(id)'"
            )

    # 5. Indexes and Unique constraints check
    if "users" in inspectable_tables:
        if not has_unique_constraint_or_index("users", ["email"], "ix_users_email"):
            errors.append(
                "Table 'users' missing unique index/constraint on 'email' ('ix_users_email')"
            )

    if "albums" in inspectable_tables:
        if not has_index("albums", ["user_id"], "ix_albums_user_id"):
            errors.append(
                "Table 'albums' missing index on 'user_id' ('ix_albums_user_id')"
            )
        if not has_unique_constraint_or_index(
            "albums", ["generation_id"], "ix_albums_generation_id"
        ):
            errors.append(
                "Table 'albums' missing unique index on 'generation_id' ('ix_albums_generation_id')"
            )
        if not has_index(
            "albums", ["user_id", "created_at"], "idx_albums_user_created"
        ):
            errors.append(
                "Table 'albums' missing index on ['user_id', 'created_at'] ('idx_albums_user_created')"
            )

    if "photos" in inspectable_tables:
        if not has_index("photos", ["album_id"], "ix_photos_album_id"):
            errors.append(
                "Table 'photos' missing index on 'album_id' ('ix_photos_album_id')"
            )
        if not has_unique_constraint_or_index(
            "photos", ["album_id", "order_index"], "uq_photos_album_order"
        ):
            errors.append(
                "Table 'photos' missing unique constraint/index on ['album_id', 'order_index'] ('uq_photos_album_order')"
            )

    # 6. Check constraints check
    if "photos" in inspectable_tables:
        try:
            chks = inspector.get_check_constraints("photos", schema=schema)
            has_order_chk = any(
                chk.get("name") == "chk_photos_order_index"
                or ("order_index" in (chk.get("sqltext") or ""))
                for chk in chks
            )
        except Exception:
            has_order_chk = True
        if not has_order_chk:
            errors.append(
                "Table 'photos' missing check constraint 'chk_photos_order_index' on 'order_index'"
            )

    return errors


async def wait_for_database(db_engine: AsyncEngine) -> None:
    """Ensure database connection is ready before checking baseline status."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with db_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection successfully established.")
            return
        except Exception as exc:
            if attempt == MAX_RETRIES:
                logger.error(
                    "Could not connect to database after %d attempts: %s",
                    MAX_RETRIES,
                    exc,
                )
                raise
            logger.warning(
                "Database not ready yet (attempt %d/%d). Retrying in %ds...",
                attempt,
                MAX_RETRIES,
                RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)


async def check_and_apply_baseline(db_engine: AsyncEngine) -> Optional[str]:
    """Inspect the database schema and safely establish a baseline stamp if needed.

    Returns:
        The action performed: 'already_versioned', 'clean_db', or 'stamped_0001'.

    Raises:
        IncompatibleSchemaError: If pre-existing schema is partial or incompatible with revision '0001'.
    """
    schema = "public" if db_engine.dialect.name == "postgresql" else None

    async with db_engine.begin() as conn:
        # 1. Check if alembic_version table exists and has a recorded version
        def get_db_info(sync_conn):
            insp = inspect(sync_conn)
            tables = set(insp.get_table_names(schema=schema))
            return "alembic_version" in tables, tables

        alembic_table_exists, all_tables = await conn.run_sync(get_db_info)

        if alembic_table_exists:
            version_result = await conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            current_version = version_result.scalar_one_or_none()
            if current_version:
                logger.info(
                    "Database is already tracked by Alembic at revision '%s'. No baseline required.",
                    current_version,
                )
                return "already_versioned"

        app_tables = all_tables - {"alembic_version"}

        # 2. If no application tables exist, it is a clean database
        if not app_tables:
            logger.info(
                "Clean database detected (no application tables). Ready for standard Alembic migration."
            )
            return "clean_db"

        # 3. Pre-existing application tables detected without an Alembic revision stamp:
        # Validate full schema fingerprint against revision '0001'
        logger.info(
            "Pre-existing schema detected without Alembic tracking (%d tables: %s). Validating revision '0001' fingerprint...",
            len(app_tables),
            sorted(list(app_tables)),
        )

        def validate_sync(sync_conn):
            insp = inspect(sync_conn)
            return validate_schema_fingerprint(insp, schema=schema)

        discrepancies = await conn.run_sync(validate_sync)

        if discrepancies:
            formatted_errors = "\n  - ".join(discrepancies)
            msg = (
                f"Pre-existing database schema does not match Alembic revision '0001' fingerprint:\n  - {formatted_errors}"
            )
            logger.error(msg)
            raise IncompatibleSchemaError(msg)

        logger.info(
            "Database schema matches revision '0001' fingerprint. Establishing baseline stamp..."
        )

        # 4. Stamp baseline version 0001
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "  version_num VARCHAR(32) NOT NULL,"
                "  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO alembic_version (version_num) VALUES ('0001') ON CONFLICT DO NOTHING"
            )
        )
        logger.info(
            "Successfully established baseline and stamped Alembic revision '0001'."
        )
        return "stamped_0001"


async def main() -> None:
    try:
        await wait_for_database(engine)
        await check_and_apply_baseline(engine)
    except IncompatibleSchemaError as exc:
        logger.critical("Baseline validation failed: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.critical(
            "Baseline process encountered an unexpected error: %s", exc
        )
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
