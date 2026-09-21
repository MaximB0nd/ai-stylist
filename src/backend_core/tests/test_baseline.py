from unittest.mock import AsyncMock, MagicMock
import pytest
from app.db.baseline import (
    EXPECTED_COLUMNS,
    IncompatibleSchemaError,
    check_and_apply_baseline,
    validate_schema_fingerprint,
)


def _build_valid_mock_inspector() -> MagicMock:
    """Create a mock Inspector representing a complete, valid revision 0001 schema."""
    insp = MagicMock()
    insp.get_table_names.return_value = ["users", "albums", "photos"]
    insp.get_columns.side_effect = lambda t, schema=None: [
        {"name": col} for col in EXPECTED_COLUMNS[t]
    ]
    insp.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    insp.get_foreign_keys.side_effect = lambda t, schema=None: (
        [
            {
                "referred_table": "users",
                "constrained_columns": ["user_id"],
                "referred_columns": ["id"],
            }
        ]
        if t == "albums"
        else [
            {
                "referred_table": "albums",
                "constrained_columns": ["album_id"],
                "referred_columns": ["id"],
            }
        ]
        if t == "photos"
        else []
    )
    insp.get_indexes.side_effect = lambda t, schema=None: (
        [
            {
                "name": "ix_users_email",
                "column_names": ["email"],
                "unique": True,
            }
        ]
        if t == "users"
        else [
            {
                "name": "ix_albums_user_id",
                "column_names": ["user_id"],
                "unique": False,
            },
            {
                "name": "ix_albums_generation_id",
                "column_names": ["generation_id"],
                "unique": True,
            },
            {
                "name": "idx_albums_user_created",
                "column_names": ["user_id", "created_at"],
                "unique": False,
            },
        ]
        if t == "albums"
        else [
            {
                "name": "ix_photos_album_id",
                "column_names": ["album_id"],
                "unique": False,
            }
        ]
        if t == "photos"
        else []
    )
    insp.get_unique_constraints.side_effect = lambda t, schema=None: (
        [
            {
                "name": "uq_photos_album_order",
                "column_names": ["album_id", "order_index"],
            }
        ]
        if t == "photos"
        else []
    )
    insp.get_check_constraints.side_effect = lambda t, schema=None: (
        [
            {
                "name": "chk_photos_order_index",
                "sqltext": "order_index >= 0 AND order_index < 10",
            }
        ]
        if t == "photos"
        else []
    )
    return insp


# ==============================================================================
# Async check_and_apply_baseline scenario tests
# ==============================================================================


@pytest.mark.asyncio
async def test_baseline_already_versioned():
    mock_conn = AsyncMock()
    mock_conn.run_sync.return_value = (
        True,
        {"alembic_version", "users", "albums", "photos"},
    )

    mock_version_res = MagicMock()
    mock_version_res.scalar_one_or_none.return_value = "0001"
    mock_conn.execute.return_value = mock_version_res

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    result = await check_and_apply_baseline(mock_engine)
    assert result == "already_versioned"
    assert mock_conn.execute.call_count == 1


@pytest.mark.asyncio
async def test_baseline_clean_database():
    mock_conn = AsyncMock()
    mock_conn.run_sync.return_value = (False, set())

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    result = await check_and_apply_baseline(mock_engine)
    assert result == "clean_db"
    assert mock_conn.execute.call_count == 0


@pytest.mark.asyncio
async def test_baseline_stamps_matching_legacy_schema():
    mock_conn = AsyncMock()
    mock_conn.run_sync.side_effect = [
        (False, {"users", "albums", "photos"}),
        [],  # validation errors empty -> schema matches 0001
    ]

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    result = await check_and_apply_baseline(mock_engine)
    assert result == "stamped_0001"
    # CREATE TABLE alembic_version and INSERT INTO alembic_version executed
    assert mock_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_baseline_partial_schema_raises_error():
    mock_conn = AsyncMock()
    mock_conn.run_sync.side_effect = [
        (False, {"users"}),
        ["Missing required table(s): ['albums', 'photos']"],
    ]

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    with pytest.raises(IncompatibleSchemaError) as exc_info:
        await check_and_apply_baseline(mock_engine)

    assert "Missing required table(s): ['albums', 'photos']" in str(
        exc_info.value
    )
    # Ensure no alembic_version table or stamp was written
    assert mock_conn.execute.call_count == 0


@pytest.mark.asyncio
async def test_baseline_incompatible_schema_raises_error():
    mock_conn = AsyncMock()
    mock_conn.run_sync.side_effect = [
        (False, {"users", "albums", "photos"}),
        ["Table 'albums' missing column(s): ['shoes']"],
    ]

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    with pytest.raises(IncompatibleSchemaError) as exc_info:
        await check_and_apply_baseline(mock_engine)

    assert "Table 'albums' missing column(s): ['shoes']" in str(exc_info.value)
    # Ensure no stamp was written
    assert mock_conn.execute.call_count == 0


# ==============================================================================
# validate_schema_fingerprint unit tests
# ==============================================================================


def test_fingerprint_valid_full_schema():
    insp = _build_valid_mock_inspector()
    errors = validate_schema_fingerprint(insp)
    assert errors == []


def test_fingerprint_missing_tables():
    insp = _build_valid_mock_inspector()
    insp.get_table_names.return_value = ["users"]
    errors = validate_schema_fingerprint(insp)
    assert any("Missing required table(s)" in err for err in errors)
    assert any("albums" in err and "photos" in err for err in errors)


def test_fingerprint_unexpected_tables():
    insp = _build_valid_mock_inspector()
    insp.get_table_names.return_value = [
        "users",
        "albums",
        "photos",
        "legacy_orders",
    ]
    errors = validate_schema_fingerprint(insp)
    assert any("Unexpected table(s)" in err for err in errors)
    assert any("legacy_orders" in err for err in errors)


def test_fingerprint_missing_columns():
    insp = _build_valid_mock_inspector()
    insp.get_columns.side_effect = lambda t, schema=None: (
        [{"name": col} for col in EXPECTED_COLUMNS[t] if col != "shoes"]
        if t == "albums"
        else [{"name": col} for col in EXPECTED_COLUMNS[t]]
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'albums' missing column(s): ['shoes']" in err for err in errors
    )


def test_fingerprint_unexpected_columns():
    insp = _build_valid_mock_inspector()
    insp.get_columns.side_effect = lambda t, schema=None: (
        [{"name": col} for col in EXPECTED_COLUMNS[t]]
        + [{"name": "avatar_url"}]
        if t == "users"
        else [{"name": col} for col in EXPECTED_COLUMNS[t]]
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'users' has unexpected column(s): ['avatar_url']" in err
        for err in errors
    )


def test_fingerprint_invalid_primary_key():
    insp = _build_valid_mock_inspector()
    insp.get_pk_constraint.side_effect = lambda t, schema=None: (
        {"constrained_columns": ["email"]}
        if t == "users"
        else {"constrained_columns": ["id"]}
    )
    errors = validate_schema_fingerprint(insp)
    assert any("Table 'users' invalid primary key" in err for err in errors)


def test_fingerprint_missing_foreign_keys():
    insp = _build_valid_mock_inspector()
    insp.get_foreign_keys.side_effect = lambda t, schema=None: []
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'albums' missing foreign key on 'user_id'" in err
        for err in errors
    )
    assert any(
        "Table 'photos' missing foreign key on 'album_id'" in err
        for err in errors
    )


def test_fingerprint_missing_indexes():
    insp = _build_valid_mock_inspector()
    insp.get_indexes.side_effect = lambda t, schema=None: []
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'albums' missing index on 'user_id'" in err for err in errors
    )
    assert any(
        "Table 'albums' missing index on ['user_id', 'created_at']" in err
        for err in errors
    )
    assert any(
        "Table 'photos' missing index on 'album_id'" in err for err in errors
    )


def test_fingerprint_missing_unique_constraint():
    insp = _build_valid_mock_inspector()
    insp.get_unique_constraints.side_effect = lambda t, schema=None: []
    insp.get_indexes.side_effect = lambda t, schema=None: [
        {"name": "ix_users_email", "column_names": ["email"], "unique": False}
    ]
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'users' missing unique index/constraint on 'email'" in err
        for err in errors
    )


def test_fingerprint_missing_check_constraint():
    insp = _build_valid_mock_inspector()
    insp.get_check_constraints.side_effect = lambda t, schema=None: []
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'photos' missing check constraint 'chk_photos_order_index'"
        in err
        for err in errors
    )
