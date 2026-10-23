"""Admin access, migration and completion timestamps against disposable PostgreSQL."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx
import pytest
from sqlalchemy import text, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings
from app.core.security import hash_password
from app.db.repositories.album_repository import AlbumRepository
from app.models.album import Album
from tests.test_feedback_postgres import migrate


async def test_admin_real_postgres_readonly_role_and_completion(monkeypatch):
    supplied = os.environ.get("FEEDBACK_TEST_DATABASE_URL")
    if not supplied: pytest.skip("Set FEEDBACK_TEST_DATABASE_URL to a disposable PostgreSQL server")
    base = make_url(supplied)
    admin = await asyncpg.connect(base.set(drivername="postgresql").render_as_string(hide_password=False))
    name = "admin_test_" + uuid.uuid4().hex
    url = base.set(drivername="postgresql+asyncpg", database=name).render_as_string(hide_password=False)
    engine, created = None, False
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
        created = True
        migrate(url, "0007")
        engine = create_async_engine(url)
        user_id, other_id, album_id, token, remote_id = [uuid.uuid4() for _ in range(5)]
        password = "Admin-Integration-123!"
        hashed = await hash_password(password)
        async with engine.begin() as conn:
            for identity, email in ((user_id, "admin@example.com"), (other_id, "normal@example.com")):
                await conn.execute(text("INSERT INTO users(id,email,password_hash,name) VALUES (:id,:email,:hash,'Test')"), {"id":identity,"email":email,"hash":hashed})
            await conn.execute(text("""INSERT INTO albums(id,user_id,generation_id,title,situation,status)
                VALUES (:id,:uid,:gid,'Old task','office','COMPLETED')"""), {"id":uuid.uuid4(),"uid":user_id,"gid":uuid.uuid4()})
        migrate(url, "head")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            assert await session.scalar(text("SELECT count(*) FROM users WHERE is_admin")) == 0
            assert await session.scalar(text("SELECT finished_at FROM albums LIMIT 1")) is None
            await session.execute(text("UPDATE users SET is_admin=true WHERE id=:id"), {"id":user_id})
            session.add(Album(id=album_id,user_id=user_id,generation_id=uuid.uuid4(),title="Generated",situation="office",
                status="DOWNLOADING",ai_job_id=remote_id,processing_token=token,lease_expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)))
            await session.commit()
            repo = AlbumRepository(session)
            old = await session.scalar(select(Album).where(Album.title == "Old task"))
            old = await repo.update_status(old.id, "COMPLETED")
            assert old.finished_at is None
            assert await repo.complete_with_photos(album_id,[{"order_index":0,"object_key":"test.png"}],token,ack_job_id=remote_id)
            end = await session.scalar(text("SELECT finished_at FROM albums WHERE id=:id"), {"id":album_id})
            assert end is not None
            await repo.record_result_ack(album_id,remote_id,pending=False)
            assert await session.scalar(text("SELECT finished_at FROM albums WHERE id=:id"), {"id":album_id}) == end
            task = await repo.create_album(user_id=user_id,generation_id=uuid.uuid4(),title="Fail",situation="office",styles=[],shoes=[],impressions=[])
            task_id = task.id
            lease = await repo.claim_work(task_id,["VALIDATING"])
            assert await repo.finish_work(task_id,lease,status="FAILED")
            assert await session.scalar(text("SELECT finished_at FROM albums WHERE id=:id"), {"id":task_id}) is not None
        from app.admin import app as admin_app
        from app.services import admin_service
        monkeypatch.setattr(settings,"ADMIN_SECRET_KEY","admin-postgres-test-secret-separate-32chars")
        application = admin_app.create_admin_app()
        from app.admin import models
        for module in (admin_app,admin_service,models): monkeypatch.setattr(module,"AsyncSessionLocal",sessions)
        for klass in (models.UserAdmin,models.GenerationAdmin,models.AlbumAdmin): monkeypatch.setattr(klass,"db_session_maker",sessions)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application),base_url="http://test") as client:
            assert (await client.post("/data/api/sign-in",json={"username":"normal@example.com","password":password})).status_code == 401
            login = await client.post("/data/api/sign-in",json={"username":"admin@example.com","password":password})
            assert login.status_code == 200, login.text
            assert "httponly" in login.headers["set-cookie"].lower()
            for model in ("User","Album","GenerationRecord"):
                response = await client.get(f"/data/api/list/{model}")
                assert response.status_code == 200, response.text
                assert hashed not in response.text and "password_hash" not in response.text
                assert "dispatch_request" not in response.text
            assert (await client.get("/data/api/configuration")).status_code == 200
            assert (await client.get("/overview")).status_code == 200
            assert (await client.get("/generations?status=FAILED")).status_code == 200
            assert (await client.patch(f"/data/api/change/User/{user_id}",json={"is_admin":False})).status_code == 403
            async with sessions() as session:
                await session.execute(text("UPDATE users SET is_admin=false WHERE id=:id"), {"id":user_id})
                await session.commit()
            assert (await client.get("/data/api/list/User")).status_code == 401
        await engine.dispose()
        migrate(url,"0007",downgrade=True)
        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT count(*) FROM users")) == 2
        migrate(url,"head")
    finally:
        if engine is not None: await engine.dispose()
        try:
            if created: await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally: await admin.close()
