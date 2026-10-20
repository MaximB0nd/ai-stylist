"""Exercise the delivery outbox migration and atomic commit against PostgreSQL."""
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.repositories.album_repository import AlbumRepository
from app.services import generation_ack
from tests.test_feedback_postgres import migrate


async def test_delivery_outbox_atomicity_restart_and_cooldown(monkeypatch):
    supplied = os.environ.get("FEEDBACK_TEST_DATABASE_URL")
    if not supplied:
        pytest.skip("Set FEEDBACK_TEST_DATABASE_URL to a disposable PostgreSQL test server")
    base = make_url(supplied)
    admin = await asyncpg.connect(base.set(drivername="postgresql").render_as_string(hide_password=False))
    name = "delivery_test_" + uuid.uuid4().hex
    url = base.set(drivername="postgresql+asyncpg", database=name).render_as_string(hide_password=False)
    engine, created = None, False
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
        created = True
        migrate(url, "0006")
        engine = create_async_engine(url)
        user_id, album_id, job_id, token = [uuid.uuid4() for _ in range(4)]
        async with engine.begin() as conn:
            await conn.execute(text("INSERT INTO users (id,email,password_hash,name) VALUES (:id,'test@example.com','test','Test')"), {"id": user_id})
            await conn.execute(text("""INSERT INTO albums (id,user_id,generation_id,title,situation,status,ai_job_id,
                processing_token,lease_expires_at) VALUES (:id,:user_id,:generation_id,'Test','office','DOWNLOADING',:job_id,
                :token,now()+interval '10 minutes')"""), {
                    "id": album_id, "user_id": user_id, "generation_id": uuid.uuid4(), "job_id": job_id, "token": token,
                })
        migrate(url, "head")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            repo = AlbumRepository(session)
            # The photo constraint fails after the album UPDATE: both must roll back.
            with pytest.raises(IntegrityError):
                await repo.complete_with_photos(album_id, [{"order_index": -1, "object_key": "bad.png"}], token, ack_job_id=job_id)
            row = (await session.execute(text("SELECT status,results_ack_pending FROM albums WHERE id=:id"), {"id": album_id})).one()
            assert row == ("DOWNLOADING", False)
            assert await session.scalar(text("SELECT count(*) FROM photos")) == 0
            photos = [{"order_index": i, "object_key": f"albums/{album_id}/{token}/look_{i:02d}.png"} for i in range(5)]
            assert await repo.complete_with_photos(album_id, photos, token, ack_job_id=job_id)
        # A new session/process sees both the photos and the pending ACK.
        async with sessions() as session:
            assert await session.scalar(text("SELECT count(*) FROM photos")) == 5
            assert await AlbumRepository(session).get_pending_result_acks() == [(album_id, job_id)]
            future = datetime.now(timezone.utc) + timedelta(minutes=10)
            await AlbumRepository(session).record_result_ack(album_id, job_id, pending=True, next_attempt_at=future)
            assert await AlbumRepository(session).get_pending_result_acks() == []
            await AlbumRepository(session).record_result_ack(album_id, job_id, pending=True)
        monkeypatch.setattr(generation_ack, "AsyncSessionLocal", sessions)
        ai = SimpleNamespace(acknowledge_results=AsyncMock())
        assert await generation_ack.recover_result_acks(ai) == 1
        ai.acknowledge_results.assert_awaited_once_with(job_id)
        async with sessions() as session:
            assert await AlbumRepository(session).get_pending_result_acks() == []
            row = (await session.execute(text("SELECT status,total_photos FROM albums WHERE id=:id"), {"id": album_id})).one()
            assert row == ("COMPLETED", 5)
            # Respect a persisted Retry-After for active jobs, but not beyond their deadline.
            await session.execute(text("""UPDATE albums SET status='QUEUED',updated_at=now()-interval '2 minutes',
                next_retry_at=now()+interval '10 minutes' WHERE id=:id"""), {"id": album_id})
            await session.commit()
            assert await AlbumRepository(session).get_recoverable_albums() == []
            await session.execute(text("UPDATE albums SET created_at=now()-interval '2 days' WHERE id=:id"), {"id": album_id})
            await session.commit()
            assert len(await AlbumRepository(session).get_recoverable_albums()) == 1
        await engine.dispose()
        migrate(url, "0006", downgrade=True)
        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT count(*) FROM photos")) == 5
            assert await conn.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_name='albums' AND column_name='results_ack_pending'")) == 0
        migrate(url, "head")
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            if created:
                await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally:
            await admin.close()
