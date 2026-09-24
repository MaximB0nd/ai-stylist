import asyncio
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ExpectedColumn:
    name: str
    type_name: str
    length: Optional[int] = None
    nullable: bool = False
    server_default: Optional[str] = None


EXPECTED_METADATA = {
    "users": [
        ExpectedColumn(
            "id", "UUID", nullable=False, server_default="gen_random_uuid()"
        ),
        ExpectedColumn(
            "email",
            "VARCHAR",
            length=255,
            nullable=False,
            server_default=None,
        ),
        ExpectedColumn(
            "password_hash",
            "VARCHAR",
            length=255,
            nullable=False,
            server_default=None,
        ),
        ExpectedColumn(
            "name", "VARCHAR", length=100, nullable=False, server_default=None
        ),
        ExpectedColumn(
            "is_active", "BOOLEAN", nullable=False, server_default="true"
        ),
        ExpectedColumn(
            "created_at", "TIMESTAMP", nullable=False, server_default="now()"
        ),
        ExpectedColumn(
            "updated_at", "TIMESTAMP", nullable=False, server_default="now()"
        ),
    ],
    "albums": [
        ExpectedColumn(
            "id", "UUID", nullable=False, server_default="gen_random_uuid()"
        ),
        ExpectedColumn(
            "user_id", "UUID", nullable=False, server_default=None
        ),
        ExpectedColumn(
            "generation_id", "UUID", nullable=False, server_default=None
        ),
        ExpectedColumn(
            "title", "VARCHAR", length=100, nullable=False, server_default=None
        ),
        ExpectedColumn(
            "situation",
            "VARCHAR",
            length=50,
            nullable=False,
            server_default=None,
        ),
        ExpectedColumn(
            "styles", "JSONB", nullable=False, server_default="'[]'::jsonb"
        ),
        ExpectedColumn(
            "shoes", "JSONB", nullable=False, server_default="'[]'::jsonb"
        ),
        ExpectedColumn(
            "impressions",
            "JSONB",
            nullable=False,
            server_default="'[]'::jsonb",
        ),
        ExpectedColumn(
            "user_age", "SMALLINT", nullable=True, server_default=None
        ),
        ExpectedColumn(
            "user_height", "SMALLINT", nullable=True, server_default=None
        ),
        ExpectedColumn(
            "user_weight", "SMALLINT", nullable=True, server_default=None
        ),
        ExpectedColumn(
            "source_face_key",
            "VARCHAR",
            length=512,
            nullable=True,
            server_default=None,
        ),
        ExpectedColumn(
            "source_body_key",
            "VARCHAR",
            length=512,
            nullable=True,
            server_default=None,
        ),
        ExpectedColumn(
            "total_photos", "INTEGER", nullable=False, server_default="10"
        ),
        ExpectedColumn(
            "is_archived", "BOOLEAN", nullable=False, server_default="false"
        ),
        ExpectedColumn(
            "created_at", "TIMESTAMP", nullable=False, server_default="now()"
        ),
        ExpectedColumn(
            "updated_at", "TIMESTAMP", nullable=False, server_default="now()"
        ),
    ],
    "photos": [
        ExpectedColumn(
            "id", "UUID", nullable=False, server_default="gen_random_uuid()"
        ),
        ExpectedColumn(
            "album_id", "UUID", nullable=False, server_default=None
        ),
        ExpectedColumn(
            "order_index", "SMALLINT", nullable=False, server_default=None
        ),
        ExpectedColumn(
            "object_key",
            "VARCHAR",
            length=512,
            nullable=False,
            server_default=None,
        ),
        ExpectedColumn(
            "is_cover", "BOOLEAN", nullable=False, server_default="false"
        ),
        ExpectedColumn(
            "is_favorite", "BOOLEAN", nullable=False, server_default="false"
        ),
        ExpectedColumn(
            "created_at", "TIMESTAMP", nullable=False, server_default="now()"
        ),
        ExpectedColumn(
            "updated_at", "TIMESTAMP", nullable=False, server_default="now()"
        ),
    ],
}

EXPECTED_INDEXES = {
    "users": [
        ("ix_users_email", ["email"], True),
    ],
    "albums": [
        ("idx_albums_user_created", ["user_id", "created_at"], False),
        ("ix_albums_generation_id", ["generation_id"], True),
        ("ix_albums_user_id", ["user_id"], False),
    ],
    "photos": [
        ("ix_photos_album_id", ["album_id"], False),
        ("uq_photos_album_order", ["album_id", "order_index"], True),
    ],
}


class IncompatibleSchemaError(RuntimeError):
    """Raised when existing database schema does not match the revision 0001 fingerprint."""

    pass


def normalize_default(raw: Optional[str]) -> Optional[str]:
    """Normalize server_default representations across PostgreSQL conventions."""
    if raw is None:
        return None
    val = raw.strip()
    if len(val) >= 2 and val[0] == "'" and val[-1] == "'":
        if not val.startswith("'[]'"):
            val = val[1:-1].strip()
    val = val.lower()
    if val in (
        "now()",
        "current_timestamp",
        "now()::timestamp with time zone",
        "current_timestamp(0)",
    ):
        return "now()"
    if val in ("true", "true::boolean"):
        return "true"
    if val in ("false", "false::boolean"):
        return "false"
    return val


def normalize_check_expr(expr: Optional[str]) -> str:
    """Normalize SQL check constraint expressions for robust canonical comparison."""
    if not expr:
        return ""
    return expr.lower().replace(" ", "").replace("(", "").replace(")", "")


def validate_schema_fingerprint(
    inspector: Inspector, schema: Optional[str] = None
) -> List[str]:
    """Validate database schema against the full fingerprint of Alembic revision '0001'.

    Follows a fail-closed principle: validates structured metadata for every column
    (type/length, nullable, normalized server_default), exact indexes/unique constraints
    (name, columns, and unique flag), foreign keys (endpoints and ON DELETE CASCADE),
    and check constraint canonical expressions.

    Returns:
        List of error descriptions if any discrepancies are found, empty list otherwise.
    """
    errors: List[str] = []

    all_tables = set(inspector.get_table_names(schema=schema))
    app_tables = all_tables - {"alembic_version"}

    expected_tables = set(EXPECTED_METADATA.keys())
    missing_tables = expected_tables - app_tables
    extra_tables = app_tables - expected_tables
    if missing_tables:
        errors.append(f"Missing required table(s): {sorted(missing_tables)}")
    if extra_tables:
        errors.append(f"Unexpected table(s): {sorted(extra_tables)}")

    inspectable_tables = expected_tables & app_tables

    # 1. Validate Columns (Type, Length, Nullable, Server Default) and Primary Keys
    for table in sorted(inspectable_tables):
        actual_cols_list = inspector.get_columns(table, schema=schema)
        actual_cols_by_name = {col["name"]: col for col in actual_cols_list}

        expected_cols = EXPECTED_METADATA[table]
        expected_col_names = {exp.name for exp in expected_cols}
        actual_col_names = set(actual_cols_by_name.keys())

        missing_cols = expected_col_names - actual_col_names
        extra_cols = actual_col_names - expected_col_names
        if missing_cols:
            errors.append(
                f"Table '{table}' missing column(s): {sorted(missing_cols)}"
            )
        if extra_cols:
            errors.append(
                f"Table '{table}' has unexpected column(s): {sorted(extra_cols)}"
            )

        for exp in expected_cols:
            if exp.name not in actual_cols_by_name:
                continue
            act = actual_cols_by_name[exp.name]
            col_type = act.get("type")
            act_type_name = type(col_type).__name__.upper()

            # Handle dialects where type name or representation may differ
            if act_type_name != exp.type_name:
                errors.append(
                    f"Table '{table}', column '{exp.name}' invalid type: expected {exp.type_name}, got {act_type_name}"
                )

            if exp.length is not None:
                act_len = getattr(col_type, "length", None)
                if act_len != exp.length:
                    errors.append(
                        f"Table '{table}', column '{exp.name}' invalid length: expected {exp.length}, got {act_len}"
                    )

            if act.get("nullable") != exp.nullable:
                errors.append(
                    f"Table '{table}', column '{exp.name}' invalid nullable: expected {exp.nullable}, got {act.get('nullable')}"
                )

            norm_default = normalize_default(act.get("default"))
            if norm_default != exp.server_default:
                errors.append(
                    f"Table '{table}', column '{exp.name}' invalid server_default: expected {exp.server_default!r}, got {norm_default!r}"
                )

        pk = inspector.get_pk_constraint(table, schema=schema)
        pk_cols = pk.get("constrained_columns") or []
        if pk_cols != ["id"]:
            errors.append(
                f"Table '{table}' invalid primary key: expected ['id'], got {pk_cols}"
            )

    # 2. Validate Foreign Keys (Endpoints and ON DELETE CASCADE)
    if "albums" in inspectable_tables:
        fks = inspector.get_foreign_keys("albums", schema=schema)
        has_fk = any(
            fk.get("constrained_columns") == ["user_id"]
            and fk.get("referred_table") == "users"
            and fk.get("referred_columns") == ["id"]
            and (fk.get("options") or {}).get("ondelete", "").upper()
            == "CASCADE"
            for fk in fks
        )
        if not has_fk:
            errors.append(
                "Table 'albums' missing foreign key: 'user_id' -> 'users(id)' ON DELETE CASCADE"
            )

    if "photos" in inspectable_tables:
        fks = inspector.get_foreign_keys("photos", schema=schema)
        has_fk = any(
            fk.get("constrained_columns") == ["album_id"]
            and fk.get("referred_table") == "albums"
            and fk.get("referred_columns") == ["id"]
            and (fk.get("options") or {}).get("ondelete", "").upper()
            == "CASCADE"
            for fk in fks
        )
        if not has_fk:
            errors.append(
                "Table 'photos' missing foreign key: 'album_id' -> 'albums(id)' ON DELETE CASCADE"
            )

    # 3. Validate Indexes and Unique Constraints (Exact Name, Columns, and Unique Flag)
    for table in sorted(inspectable_tables):
        actual_indexes = inspector.get_indexes(table, schema=schema)
        actual_uqs = inspector.get_unique_constraints(table, schema=schema)

        expected_idx_list = EXPECTED_INDEXES.get(table, [])
        expected_names = {idx[0] for idx in expected_idx_list}

        for exp_name, exp_cols, exp_unique in expected_idx_list:
            matched = any(
                idx.get("name") == exp_name
                and idx.get("column_names") == exp_cols
                and bool(idx.get("unique")) == exp_unique
                for idx in actual_indexes
            )
            if not matched and exp_unique:
                # PostgreSQL unique constraints may be returned by get_unique_constraints
                matched = any(
                    uq.get("name") == exp_name
                    and uq.get("column_names") == exp_cols
                    for uq in actual_uqs
                )
            if not matched:
                errors.append(
                    f"Table '{table}' missing expected index/unique constraint '{exp_name}': columns={exp_cols}, unique={exp_unique}"
                )

        # Fail-closed on unexpected extra indexes
        for act_idx in actual_indexes:
            act_name = act_idx.get("name")
            if (
                act_name
                and act_name not in expected_names
                and not act_name.endswith("_pkey")
            ):
                errors.append(
                    f"Table '{table}' has unexpected index '{act_name}'"
                )

    # 4. Validate Check Constraints (Canonical Expression)
    if "photos" in inspectable_tables:
        chks = inspector.get_check_constraints("photos", schema=schema)
        expected_canonical = normalize_check_expr(
            "order_index >= 0 AND order_index < 10"
        )
        has_chk = any(
            chk.get("name") == "chk_photos_order_index"
            and normalize_check_expr(chk.get("sqltext", ""))
            == expected_canonical
            for chk in chks
        )
        if not has_chk:
            errors.append(
                "Table 'photos' missing check constraint 'chk_photos_order_index' with expression 'order_index >= 0 AND order_index < 10'"
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
