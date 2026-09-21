from unittest.mock import AsyncMock, MagicMock
import os
import pytest
from app.db.baseline import (
    EXPECTED_INDEXES,
    EXPECTED_METADATA,
    IncompatibleSchemaError,
    check_and_apply_baseline,
    normalize_check_expr,
    normalize_default,
    validate_schema_fingerprint,
)


def make_mock_type(type_name: str, length: int = None):
    cls = type(
        type_name,
        (),
        {
            "length": length,
            "__str__": lambda self: f"{type_name}({length})" if length else type_name,
        },
    )
    return cls()


def _build_valid_mock_inspector() -> MagicMock:
    """Create a mock Inspector representing a complete, valid revision 0001 schema."""
    insp = MagicMock()
    insp.get_table_names.return_value = ["users", "albums", "photos"]

    def mock_get_columns(table: str, schema=None):
        cols = []
        for exp in EXPECTED_METADATA[table]:
            col_type = make_mock_type(exp.type_name, exp.length)
            cols.append(
                {
                    "name": exp.name,
                    "type": col_type,
                    "nullable": exp.nullable,
                    "default": exp.server_default,
                }
            )
        return cols

    insp.get_columns.side_effect = mock_get_columns
    insp.get_pk_constraint.return_value = {"constrained_columns": ["id"]}

    insp.get_foreign_keys.side_effect = lambda t, schema=None: (
        [
            {
                "name": "fk_albums_user_id",
                "constrained_columns": ["user_id"],
                "referred_schema": "public",
                "referred_table": "users",
                "referred_columns": ["id"],
                "options": {"ondelete": "CASCADE"},
            }
        ]
        if t == "albums"
        else [
            {
                "name": "fk_photos_album_id",
                "constrained_columns": ["album_id"],
                "referred_schema": "public",
                "referred_table": "albums",
                "referred_columns": ["id"],
                "options": {"ondelete": "CASCADE"},
            }
        ]
        if t == "photos"
        else []
    )

    insp.get_indexes.side_effect = lambda t, schema=None: [
        {
            "name": name,
            "column_names": cols,
            "unique": unique,
        }
        for name, cols, unique in EXPECTED_INDEXES.get(t, [])
    ]

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
# Async check_and_apply_baseline scenario tests (Mocked Engine)
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
    assert mock_conn.execute.call_count == 0


@pytest.mark.asyncio
async def test_baseline_incompatible_schema_raises_error():
    mock_conn = AsyncMock()
    mock_conn.run_sync.side_effect = [
        (False, {"users", "albums", "photos"}),
        ["Table 'albums', column 'shoes' invalid server_default"],
    ]

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    with pytest.raises(IncompatibleSchemaError) as exc_info:
        await check_and_apply_baseline(mock_engine)

    assert "invalid server_default" in str(exc_info.value)
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


def test_fingerprint_missing_columns():
    insp = _build_valid_mock_inspector()
    orig_cols = insp.get_columns("albums")
    insp.get_columns.side_effect = lambda t, schema=None: (
        [c for c in orig_cols if c["name"] != "shoes"]
        if t == "albums"
        else orig_cols
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'albums' missing column(s): ['shoes']" in err for err in errors
    )


def test_fingerprint_unexpected_columns():
    insp = _build_valid_mock_inspector()
    orig_cols = insp.get_columns("users")
    extra_col = {
        "name": "avatar_url",
        "type": make_mock_type("VARCHAR", 255),
        "nullable": True,
        "default": None,
    }
    insp.get_columns.side_effect = lambda t, schema=None: (
        orig_cols + [extra_col] if t == "users" else orig_cols
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'users' has unexpected column(s): ['avatar_url']" in err
        for err in errors
    )


def test_fingerprint_wrong_column_type():
    insp = _build_valid_mock_inspector()
    orig_cols = insp.get_columns("users")
    mutated = []
    for c in orig_cols:
        if c["name"] == "email":
            mutated.append({**c, "type": make_mock_type("TEXT")})
        else:
            mutated.append(c)
    insp.get_columns.side_effect = lambda t, schema=None: (
        mutated if t == "users" else orig_cols
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "column 'email' invalid type: expected VARCHAR, got TEXT" in err
        for err in errors
    )


def test_fingerprint_wrong_column_length():
    insp = _build_valid_mock_inspector()
    orig_cols = insp.get_columns("users")
    mutated = []
    for c in orig_cols:
        if c["name"] == "email":
            mutated.append({**c, "type": make_mock_type("VARCHAR", 100)})
        else:
            mutated.append(c)
    insp.get_columns.side_effect = lambda t, schema=None: (
        mutated if t == "users" else orig_cols
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "column 'email' invalid length: expected 255, got 100" in err
        for err in errors
    )


def test_fingerprint_wrong_column_nullable():
    insp = _build_valid_mock_inspector()
    orig_cols = insp.get_columns("users")
    mutated = []
    for c in orig_cols:
        if c["name"] == "email":
            mutated.append({**c, "nullable": True})
        else:
            mutated.append(c)
    insp.get_columns.side_effect = lambda t, schema=None: (
        mutated if t == "users" else orig_cols
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "column 'email' invalid nullable: expected False, got True" in err
        for err in errors
    )


def test_fingerprint_wrong_server_default():
    insp = _build_valid_mock_inspector()
    orig_cols = insp.get_columns("users")
    mutated = []
    for c in orig_cols:
        if c["name"] == "is_active":
            mutated.append({**c, "default": None})
        else:
            mutated.append(c)
    insp.get_columns.side_effect = lambda t, schema=None: (
        mutated if t == "users" else orig_cols
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "column 'is_active' invalid server_default: expected 'true', got None"
        in err
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
        "Table 'albums' missing foreign key: 'user_id' -> 'users(id)' ON DELETE CASCADE"
        in err
        for err in errors
    )
    assert any(
        "Table 'photos' missing foreign key: 'album_id' -> 'albums(id)' ON DELETE CASCADE"
        in err
        for err in errors
    )


def test_fingerprint_foreign_key_missing_cascade():
    insp = _build_valid_mock_inspector()
    insp.get_foreign_keys.side_effect = lambda t, schema=None: (
        [
            {
                "name": "fk_albums_user_id",
                "constrained_columns": ["user_id"],
                "referred_schema": "public",
                "referred_table": "users",
                "referred_columns": ["id"],
                "options": {"ondelete": "SET NULL"},
            }
        ]
        if t == "albums"
        else []
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'albums' missing foreign key: 'user_id' -> 'users(id)' ON DELETE CASCADE"
        in err
        for err in errors
    )


def test_fingerprint_missing_indexes():
    insp = _build_valid_mock_inspector()
    insp.get_indexes.side_effect = lambda t, schema=None: []
    insp.get_unique_constraints.side_effect = lambda t, schema=None: []
    errors = validate_schema_fingerprint(insp)
    assert any(
        "missing expected index/unique constraint 'ix_users_email'" in err
        for err in errors
    )
    assert any(
        "missing expected index/unique constraint 'idx_albums_user_created'"
        in err
        for err in errors
    )


def test_fingerprint_index_wrong_columns():
    insp = _build_valid_mock_inspector()
    insp.get_indexes.side_effect = lambda t, schema=None: (
        [{"name": "ix_users_email", "column_names": ["name"], "unique": True}]
        if t == "users"
        else []
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "missing expected index/unique constraint 'ix_users_email': columns=['email']"
        in err
        for err in errors
    )


def test_fingerprint_index_wrong_unique():
    insp = _build_valid_mock_inspector()
    insp.get_unique_constraints.side_effect = lambda t, schema=None: []
    insp.get_indexes.side_effect = lambda t, schema=None: (
        [{"name": "ix_users_email", "column_names": ["email"], "unique": False}]
        if t == "users"
        else []
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "missing expected index/unique constraint 'ix_users_email'" in err
        for err in errors
    )


def test_fingerprint_unexpected_index():
    insp = _build_valid_mock_inspector()
    orig_idx = [
        {"name": "ix_users_email", "column_names": ["email"], "unique": True},
        {"name": "ix_users_custom", "column_names": ["name"], "unique": False},
    ]
    insp.get_indexes.side_effect = lambda t, schema=None: (
        orig_idx if t == "users" else []
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'users' has unexpected index 'ix_users_custom'" in err
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


def test_fingerprint_check_constraint_wrong_expression():
    insp = _build_valid_mock_inspector()
    insp.get_check_constraints.side_effect = lambda t, schema=None: (
        [
            {
                "name": "chk_photos_order_index",
                "sqltext": "order_index >= -999",
            }
        ]
        if t == "photos"
        else []
    )
    errors = validate_schema_fingerprint(insp)
    assert any(
        "Table 'photos' missing check constraint 'chk_photos_order_index' with expression"
        in err
        for err in errors
    )


# ==============================================================================
# Real PostgreSQL Integration Tests
# ==============================================================================


async def _check_real_postgres_connection():
    """Verify if PostgreSQL is accessible for integration testing."""
    import asyncpg

    candidate_passwords = [
        os.getenv("POSTGRES_PASSWORD", "root"),
        "root",
        "postgres",
        "admin",
    ]
    for p in candidate_passwords:
        try:
            conn = await asyncpg.connect(
                user="postgres",
                password=p,
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                database="postgres",
            )
            await conn.close()
            return p
        except Exception:
            continue
    return None


@pytest.mark.asyncio
async def test_postgres_integration_valid_schema_and_fail_closed_mutations():
    """Integration test running against a live PostgreSQL 16+ instance.

    Verifies:
      1. Valid schema 0001 created via init.sql passes baseline validation,
         is stamped with revision '0001', and populates alembic_version.
      2. Each fail-closed mutation (wrong type, length, nullable, server_default,
         index columns, index unique, FK ondelete, check constraint) causes
         check_and_apply_baseline to fail with IncompatibleSchemaError without
         creating or stamping alembic_version.
    """
    import asyncpg
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    password = await _check_real_postgres_connection()
    if not password:
        pytest.skip("Live PostgreSQL instance not available for integration test.")

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", 5432))
    base_url = f"postgresql+asyncpg://postgres:{password}@{host}:{port}"

    # Read standalone init.sql to establish canonical baseline
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    init_sql_path = os.path.join(repo_root, "src", "backend_core", "db", "init.sql")
    with open(init_sql_path, "r", encoding="utf-8") as f:
        full_sql = f.read()

    # Isolate schema without alembic_version stamp
    sql_without_alembic = full_sql.split("-- Table: alembic_version")[0] + "COMMIT;"

    sys_conn = await asyncpg.connect(
        user="postgres", password=password, host=host, port=port, database="postgres"
    )
    try:
        await sys_conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('test_integ_canonical', 'test_integ_mut') AND pid <> pg_backend_pid();"
        )
        await sys_conn.execute("DROP DATABASE IF EXISTS test_integ_canonical;")
        await sys_conn.execute("DROP DATABASE IF EXISTS test_integ_mut;")
        await sys_conn.execute("CREATE DATABASE test_integ_canonical;")
    finally:
        await sys_conn.close()

    # Populate canonical database
    canon_conn = await asyncpg.connect(
        user="postgres",
        password=password,
        host=host,
        port=port,
        database="test_integ_canonical",
    )
    try:
        await canon_conn.execute(sql_without_alembic)
    finally:
        await canon_conn.close()

    # 1. Verify valid schema 0001 passes baseline and stamps alembic_version
    canon_engine = create_async_engine(f"{base_url}/test_integ_canonical")
    try:
        result = await check_and_apply_baseline(canon_engine)
        assert result == "stamped_0001"

        # Verify alembic_version table exists and contains '0001'
        async with canon_engine.connect() as conn:
            stamp = await conn.scalar(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            assert stamp == "0001"
    finally:
        await canon_engine.dispose()

    # 2. Verify all mutations fail closed
    mutations = [
        (
            "wrong_column_type",
            "ALTER TABLE users ALTER COLUMN email TYPE TEXT;",
        ),
        (
            "wrong_column_length",
            "ALTER TABLE users ALTER COLUMN email TYPE VARCHAR(100);",
        ),
        (
            "wrong_column_nullable",
            "ALTER TABLE users ALTER COLUMN email DROP NOT NULL;",
        ),
        (
            "wrong_server_default",
            "ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT;",
        ),
        (
            "wrong_index_columns",
            "DROP INDEX ix_users_email; CREATE UNIQUE INDEX ix_users_email ON users(name);",
        ),
        (
            "wrong_index_unique",
            "DROP INDEX ix_users_email; CREATE INDEX ix_users_email ON users(email);",
        ),
        (
            "wrong_fk_ondelete",
            "ALTER TABLE albums DROP CONSTRAINT fk_albums_user_id; ALTER TABLE albums ADD CONSTRAINT fk_albums_user_id FOREIGN KEY (user_id) REFERENCES users(id);",
        ),
        (
            "wrong_check_constraint",
            "ALTER TABLE photos DROP CONSTRAINT chk_photos_order_index; ALTER TABLE photos ADD CONSTRAINT chk_photos_order_index CHECK (order_index >= -999);",
        ),
    ]

    for name, sql in mutations:
        sys_conn = await asyncpg.connect(
            user="postgres",
            password=password,
            host=host,
            port=port,
            database="postgres",
        )
        try:
            await sys_conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'test_integ_mut' AND pid <> pg_backend_pid();"
            )
            await sys_conn.execute("DROP DATABASE IF EXISTS test_integ_mut;")
            await sys_conn.execute(
                "CREATE DATABASE test_integ_mut TEMPLATE test_integ_canonical;"
            )
        finally:
            await sys_conn.close()

        # Remove the alembic_version table stamped earlier to test legacy state with mutation
        mut_conn = await asyncpg.connect(
            user="postgres",
            password=password,
            host=host,
            port=port,
            database="test_integ_mut",
        )
        try:
            await mut_conn.execute("DROP TABLE IF EXISTS alembic_version;")
            await mut_conn.execute(sql)
        finally:
            await mut_conn.close()

        # Run check_and_apply_baseline: MUST fail and NOT stamp alembic_version
        mut_engine = create_async_engine(f"{base_url}/test_integ_mut")
        try:
            with pytest.raises(IncompatibleSchemaError):
                await check_and_apply_baseline(mut_engine)

            # Confirm alembic_version table was NOT created or filled
            async with mut_engine.connect() as conn:
                table_exists = await conn.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version')"
                    )
                )
                assert (
                    table_exists is False
                ), f"Mutation {name} unexpectedly created alembic_version table!"
        finally:
            await mut_engine.dispose()

    # Cleanup test databases
    sys_conn = await asyncpg.connect(
        user="postgres", password=password, host=host, port=port, database="postgres"
    )
    try:
        await sys_conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('test_integ_canonical', 'test_integ_mut') AND pid <> pg_backend_pid();"
        )
        await sys_conn.execute("DROP DATABASE IF EXISTS test_integ_canonical;")
        await sys_conn.execute("DROP DATABASE IF EXISTS test_integ_mut;")
    finally:
        await sys_conn.close()
