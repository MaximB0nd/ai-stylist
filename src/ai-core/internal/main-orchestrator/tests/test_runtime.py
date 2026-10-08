import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from app.db import CleanupRequest, Command, Event, Job
from app.dispatch import dispatch_one
from app.imports import process_one_import
from app.main import create_app
from app.runtime import process_cleanup, process_events, process_expirations
from app.settings import Settings
from test_jobs_api import request_body
from test_pipeline import FakeArtifacts

DATABASE_URL = os.getenv("ORCHESTRATOR_TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:55439/orchestrator_test")


@pytest.mark.asyncio
async def test_missing_callback_resends_same_command_without_new_attempt():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    sent = []
    transport = httpx.MockTransport(lambda request: (sent.append(request) or httpx.Response(202)))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=transport) as worker:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            for _ in range(2):
                assert await dispatch_one(app.state.sessions, app.state.cipher,
                                          {"PREPARATION": "https://worker.test"}, artifacts, worker, job_id)
                async with app.state.sessions.begin() as session:
                    command = (await session.execute(select(Command).where(Command.job_id == job_id,
                                                                          Command.stage == "PREPARATION"))).scalar_one()
                    command.next_send_at = datetime.now(UTC) - timedelta(seconds=1)
            assert len(sent) == 2
            assert sent[0].content == sent[1].content
            async with app.state.sessions() as session:
                assert command.attempt == 1 and command.sent_count == 2
                assert (await session.get(Job, job_id)).failed_attempt_count == 0
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_unreachable_notification_stops_after_four_deliveries():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    sent = []
    transport = httpx.MockTransport(lambda request: (sent.append(request) or httpx.Response(503)))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=transport) as worker:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            assert await process_events(app.state.sessions, app.state.cipher, job_id)
            for _ in range(4):
                assert await dispatch_one(app.state.sessions, app.state.cipher,
                                          {"NOTIFICATION": "https://worker.test"}, None, worker, job_id)
                async with app.state.sessions.begin() as session:
                    for command in (await session.execute(select(Command).where(Command.job_id == job_id,
                                                                               Command.stage == "NOTIFICATION",
                                                                               Command.status == "PENDING"))).scalars():
                        command.next_send_at = datetime.now(UTC) - timedelta(seconds=1)
            async with app.state.sessions() as session:
                event = (await session.execute(select(Event).where(Event.job_id == job_id))).scalar_one()
                assert event.delivery_status == "UNDELIVERED"
                assert (await session.get(Job, job_id)).status == "QUEUED"
            assert len(sent) == 4
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_input_expiry_fails_and_cleanup_is_durable():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            async with app.state.sessions.begin() as session:
                job = await session.get(Job, job_id)
                job.input_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            assert await process_expirations(app.state.sessions)
            async with app.state.sessions() as session:
                job = await session.get(Job, job_id)
                assert job.status == "FAILED" and job.error_code == "INPUT_EXPIRED"
                assert job.request_encrypted is None
                assert await session.get(CleanupRequest, job.face_artifact_id)
            # Deletions remain queued while the artifact service is unavailable.
            assert not await process_cleanup(app.state.sessions, None)
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_notifications_of_one_job_wait_for_previous_result():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            assert (await client.post(f"/internal/v1/jobs/{job_id}/cancel", json={})).status_code == 200
            assert await process_events(app.state.sessions, app.state.cipher, job_id)
            assert not await process_events(app.state.sessions, app.state.cipher, job_id)
            async with app.state.sessions.begin() as session:
                events = (await session.execute(select(Event).where(Event.job_id == job_id)
                                                .order_by(Event.sequence))).scalars().all()
                assert [event.delivery_status for event in events] == ["QUEUED", "PENDING"]
                events[0].delivery_status = "UNDELIVERED"
            assert await process_events(app.state.sessions, app.state.cipher, job_id)
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_cancel_ignores_late_result_and_deletes_artifacts():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            async with app.state.sessions() as session:
                command = (await session.execute(select(Command).where(Command.job_id == job_id,
                                                                       Command.stage == "PREPARATION"))).scalar_one()
                job = await session.get(Job, job_id)
                expected = {job.face_artifact_id, job.body_artifact_id}
            assert (await client.post(f"/internal/v1/jobs/{job_id}/cancel", json={})).status_code == 200
            late = await client.post("/internal/v1/worker-results", json={
                "contract_version": 1, "message_id": str(uuid4()), "command_id": command.id,
                "job_id": job_id, "stage": "PREPARATION", "attempt": 1,
                "order_index": None, "status": "SUCCEEDED", "result": {}, "error": None,
            })
            assert late.status_code == 204
            async with app.state.sessions() as session:
                assert (await session.get(Job, job_id)).status == "CANCELLED"
            for _ in range(4):
                assert await process_cleanup(app.state.sessions, artifacts, job_id)
            assert expected.issubset(set(artifacts.deleted))
            async with app.state.sessions() as session:
                requests = (await session.execute(select(CleanupRequest).where(CleanupRequest.job_id == job_id))).scalars().all()
                assert all(request.done for request in requests)
    finally:
        await app.state.engine.dispose()
