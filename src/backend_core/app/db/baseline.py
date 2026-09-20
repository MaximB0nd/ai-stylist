import asyncio
import logging
import sys
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [db.baseline] %(message)s",
)
logger = logging.getLogger("db.baseline")

MAX_RETRIES = 10
RETRY_DELAY_SECONDS = 2


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
    """
    async with db_engine.begin() as conn:
        # 1. Check if alembic_version table exists
        alembic_table_exists = (
            await conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables "
                    "  WHERE table_schema = 'public' AND table_name = 'alembic_version'"
                    ")"
                )
            )
        ).scalar()

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

        # 2. If alembic_version does not exist or is empty, check for pre-existing tables
        users_table_exists = (
            await conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables "
                    "  WHERE table_schema = 'public' AND table_name = 'users'"
                    ")"
                )
            )
        ).scalar()

        if not users_table_exists:
            logger.info(
                "Clean database detected (no 'users' table). Ready for standard Alembic migration."
            )
            return "clean_db"

        # 3. 'users' exists without an Alembic stamp: this is a pre-existing unversioned schema
        tables_res = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN ('users', 'albums', 'photos')"
            )
        )
        existing_tables = set(tables_res.scalars().all())
        logger.info(
            "Pre-existing schema detected without Alembic tracking. Found tables: %s",
            sorted(list(existing_tables)),
        )

        # Stamp baseline version 0001
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
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
