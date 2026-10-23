"""Read-only admin boundary, timing and safe telemetry unit tests."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import time
import uuid

import httpx
import jwt
import pytest

from app.core.config import settings
from app.services import admin_service, admin_monitoring_service as monitoring
from app.admin import app as admin_app
from app.services.generation_queue import GenerationQueue


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_SECRET_KEY", "admin-test-only-secret-separate-32-characters")
    return admin_app.create_admin_app()


async def test_anonymous_and_regular_user_cannot_read_admin(admin, monkeypatch):
    monkeypatch.setattr(admin_app, "administrator", AsyncMock(return_value=False))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin), base_url="http://test") as client:
        for path in ("/api/snapshot", "/data/api/list/User", "/data/api/configuration"):
            assert (await client.get(path)).status_code == 401
        assert (await client.get("/overview")).status_code == 303


async def test_even_admin_cannot_mutate_or_export(admin, monkeypatch):
    monkeypatch.setattr(admin_app, "administrator", AsyncMock(return_value=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin), base_url="http://test") as client:
        for method, path in (("POST", "/data/api/add/User"), ("PATCH", "/data/api/change/User/1"),
                             ("DELETE", "/data/api/delete/Album/1"), ("POST", "/data/api/export/User"),
                             ("PATCH", "/data/api/change-password/1"), ("POST", "/data/api/action/Album/remove")):
            response = await client.request(method, path, json={})
            assert response.status_code == 403


async def test_secret_fields_are_absent_from_serialization(admin):
    from app.admin.models import UserAdmin, GenerationAdmin, AlbumAdmin
    from app.models.user import User
    from app.models.album import Album
    from app.admin.models import GenerationRecord
    assert "password_hash" not in UserAdmin(User).get_fields_for_serialize()
    for klass, model in ((GenerationAdmin, GenerationRecord), (AlbumAdmin, Album)):
        fields = klass(model).get_fields_for_serialize()
        assert not fields.intersection({"dispatch_request", "pending_callback", "source_face_key", "source_body_key", "processing_token"})
        assert not await klass(model).has_change_permission()


def test_duration_is_frozen_after_completion_and_old_rows_unknown():
    start = datetime.now(timezone.utc) - timedelta(minutes=2)
    row = SimpleNamespace(created_at=start, finished_at=start+timedelta(seconds=42), status="COMPLETED")
    assert admin_service.duration(row) == "42 сек."
    row.finished_at = None
    assert "старая" in admin_service.duration(row)
    row.status = "PROCESSING"
    assert int(admin_service.duration(row).split()[0]) >= 120


async def test_monitoring_does_not_record_urls_or_payload(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_ENABLED", True)
    fake = SimpleNamespace(post=AsyncMock(return_value=SimpleNamespace(status_code=503)))
    await monitoring.ObservedClient(fake).post("http://secret-host/v1/jobs", json={"url":"secret"})
    data = monitoring.get_snapshot()
    assert data["ai"]["http_status"] == 503
    assert data["ai"]["operation"] == "create"
    assert "secret" not in str(data)
    fake.post.side_effect = httpx.ConnectError("sensitive URL")
    with pytest.raises(httpx.ConnectError):
        await monitoring.ObservedClient(fake).post("http://secret-host/v1/jobs")
    assert monitoring.snapshot["ai"]["error"] == "ConnectError"


async def test_worker_counter_is_restored_after_exception(monkeypatch):
    import asyncio
    from app.services import generation_results
    monkeypatch.setattr(generation_results, "_download_and_store_results", AsyncMock(side_effect=RuntimeError("test")))
    queue = GenerationQueue()
    queue.start()
    try:
        assert queue.submit(uuid.uuid4(), uuid.uuid4(), object())
        await asyncio.wait_for(queue.queue.join(), 1)
        assert queue.active_workers == 0
    finally: await queue.close()


def test_error_redaction_removes_signed_urls():
    assert "Signature" not in admin_service.safe_error("failed http://minio/object?Signature=secret")


def test_admin_requires_separate_strong_secret():
    from app.core.config import Settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(ADMIN_ENABLED=True, ADMIN_SECRET_KEY="weak")
    with pytest.raises(ValidationError):
        Settings(ADMIN_ENABLED=True, ADMIN_SECRET_KEY=settings.SECRET_KEY)


async def test_admin_shell_query_cannot_inject_markup(admin, monkeypatch):
    monkeypatch.setattr(admin_app, "administrator", AsyncMock(return_value=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin), base_url="http://test") as client:
        response = await client.get("/users", params={"label": "<script>bad()</script>", "model": "malicious"})
        assert response.status_code == 200
        assert "bad()" not in response.text and "malicious" not in response.text
