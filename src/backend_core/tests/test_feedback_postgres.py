"""Verify real migrations and feedback persistence in a disposable PostgreSQL database.

Set FEEDBACK_TEST_DATABASE_URL to a test server whose user can CREATE DATABASE.
Only a new database with a generated feedback_test_ prefix is migrated/dropped.
"""

import os
from pathlib import Path
import subprocess
import sys
import uuid

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.repositories.feedback_repository import FeedbackRepository
from app.db.session import get_db
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def migrate(database_url, target, downgrade=False):
    env = {**os.environ, "DATABASE_URL": database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade" if downgrade else "upgrade", target],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def test_feedback_real_postgres_migration_persistence_and_cascade():
    supplied = os.environ.get("FEEDBACK_TEST_DATABASE_URL")
    if not supplied:
        pytest.skip("Set FEEDBACK_TEST_DATABASE_URL to a disposable PostgreSQL test server")
    base = make_url(supplied)
    admin = await asyncpg.connect(base.set(drivername="postgresql").render_as_string(hide_password=False))
    database_name = "feedback_test_" + uuid.uuid4().hex
    database_url = base.set(drivername="postgresql+asyncpg", database=database_name).render_as_string(hide_password=False)
    engine = None
    created = False
    try:
        await admin.execute(f'CREATE DATABASE "{database_name}"')
        created = True
        migrate(database_url, "0005")
        engine = create_async_engine(database_url)
        user_id = uuid.uuid4()
        async with engine.begin() as connection:
            await connection.execute(text(
                "INSERT INTO users (id, email, password_hash, name) VALUES (:id, :email, :password, :name)"
            ), {"id": user_id, "email": "account@example.com", "password": "test-only-hash", "name": "Account name"})
        migrate(database_url, "head")
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def database_dependency():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = database_dependency
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/feedback", headers={
                "Authorization": f"Bearer {create_access_token(subject=user_id)}",
            }, json={"name": "Contact", "email": "reply@example.com", "comment": "Saved feedback"})
        assert response.status_code == 201
        # Read in a new session: response success must mean the data is committed.
        async with sessions() as session:
            row = (await session.execute(text("SELECT * FROM feedback"))).mappings().one()
            assert str(row["id"]) == response.json()["id"]
            assert row["user_id"] == user_id
            assert (row["name"], row["email"], row["comment"]) == ("Contact", "reply@example.com", "Saved feedback")
            assert row["created_at"].tzinfo is not None
            assert (await session.execute(text("SELECT name, email FROM users WHERE id=:id"), {"id": user_id})).one() == (
                "Account name", "account@example.com",
            )
            with pytest.raises(IntegrityError):
                await FeedbackRepository(session).create(
                    user_id=uuid.uuid4(), name="Contact", email="reply@example.com", comment="Unknown user",
                )
            assert await session.scalar(text("SELECT count(*) FROM feedback")) == 1
            await session.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
            await session.commit()
        async with sessions() as session:
            assert await session.scalar(text("SELECT count(*) FROM feedback")) == 0
        await engine.dispose()
        migrate(database_url, "0005", downgrade=True)
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT to_regclass('public.feedback')")) is None
            assert await connection.scalar(text("SELECT to_regclass('public.users')")) == "users"
        migrate(database_url, "head")
    finally:
        app.dependency_overrides.pop(get_db, None)
        if engine is not None:
            await engine.dispose()
        try:
            if created:
                await admin.execute(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        finally:
            await admin.close()
