from unittest.mock import AsyncMock, MagicMock
import pytest
from app.db.baseline import check_and_apply_baseline


@pytest.mark.asyncio
async def test_baseline_already_versioned():
    mock_conn = AsyncMock()
    # 1. alembic_table_exists returns True
    mock_scalar_alembic = MagicMock()
    mock_scalar_alembic.scalar.return_value = True

    # 2. current_version returns '0001'
    mock_version_res = MagicMock()
    mock_version_res.scalar_one_or_none.return_value = "0001"

    mock_conn.execute.side_effect = [mock_scalar_alembic, mock_version_res]

    mock_engine = MagicMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    result = await check_and_apply_baseline(mock_engine)
    assert result == "already_versioned"
    # Verify no INSERT or CREATE TABLE for alembic_version was executed
    assert mock_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_baseline_clean_database():
    mock_conn = AsyncMock()
    # 1. alembic_table_exists returns False
    mock_scalar_alembic = MagicMock()
    mock_scalar_alembic.scalar.return_value = False

    # 2. users_table_exists returns False
    mock_scalar_users = MagicMock()
    mock_scalar_users.scalar.return_value = False

    mock_conn.execute.side_effect = [mock_scalar_alembic, mock_scalar_users]

    mock_engine = MagicMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    result = await check_and_apply_baseline(mock_engine)
    assert result == "clean_db"
    assert mock_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_baseline_stamps_legacy_schema():
    mock_conn = AsyncMock()
    # 1. alembic_table_exists returns False
    mock_scalar_alembic = MagicMock()
    mock_scalar_alembic.scalar.return_value = False

    # 2. users_table_exists returns True
    mock_scalar_users = MagicMock()
    mock_scalar_users.scalar.return_value = True

    # 3. existing tables query
    mock_tables_res = MagicMock()
    mock_tables_res.scalars.return_value.all.return_value = ["users", "albums", "photos"]

    # 4. CREATE TABLE alembic_version
    mock_create_res = MagicMock()

    # 5. INSERT INTO alembic_version
    mock_insert_res = MagicMock()

    mock_conn.execute.side_effect = [
        mock_scalar_alembic,
        mock_scalar_users,
        mock_tables_res,
        mock_create_res,
        mock_insert_res,
    ]

    mock_engine = MagicMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    result = await check_and_apply_baseline(mock_engine)
    assert result == "stamped_0001"
    assert mock_conn.execute.call_count == 5
