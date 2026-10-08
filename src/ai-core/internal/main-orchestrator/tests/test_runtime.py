import asyncio
import json
import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from app.db import CleanupRequest, Command, Job
from app.dispatch import dispatch_one
from app.imports import process_one_import
from app.main import create_app
from app.runtime import process_cleanup, process_expirations
from app.settings import Settings
from test_jobs_api import request_body
from test_pipeline import FakeArtifacts

DATABASE_URL = os.getenv("ORCHESTRATOR_TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:55439/orchestrator_test")


@pytest.mark.asyncio
async def test_capacity_wait_reuses_request_then_worker_failure_creates_retry():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    responses = iter([httpx.Response(429, headers={"Retry-After": "1"}),
                      httpx.Response(503, json={"code": "MODEL_UNAVAILABLE", "retryable": True})])
    sent = []
    def worker(request):
        sent.append(json.loads(request.content)["request_id"])
        return next(responses)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=httpx.MockTransport(worker)) as worker_client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await dispatch_one(app.state.sessions, app.state.cipher,
                               {"FACE_VALIDATION": "https://worker.test"}, artifacts, worker_client, job_id)
            async with app.state.sessions.begin() as session:
                command = (await session.execute(select(Command).where(Command.job_id == job_id))).scalar_one()
                assert command.attempt == 1 and command.status == "PENDING"
                command.next_send_at = datetime.now(UTC) - timedelta(seconds=1)
            await dispatch_one(app.state.sessions, app.state.cipher,
                               {"FACE_VALIDATION": "https://worker.test"}, artifacts, worker_client, job_id)
            assert sent == [sent[0], sent[0]]
            async with app.state.sessions() as session:
                commands = (await session.execute(select(Command).where(Command.job_id == job_id))).scalars().all()
                assert len(commands) == 2 and {command.attempt for command in commands} == {1, 2}
                assert (await session.get(Job, job_id)).failed_attempt_count == 1
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_cancel_ignores_late_http_response_and_cleans_artifacts():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    started, release = asyncio.Event(), asyncio.Event()
    async def worker(request):
        started.set()
        await release.wait()
        return httpx.Response(200, json={"request_id": json.loads(request.content)["request_id"],
                                         "decision": "ACCEPTED", "reasons": [],
                                         "model_version": "model-1"})
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=httpx.MockTransport(worker)) as worker_client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            task = asyncio.create_task(dispatch_one(app.state.sessions, app.state.cipher,
                {"FACE_VALIDATION": "https://worker.test"}, artifacts, worker_client, job_id))
            await asyncio.wait_for(started.wait(), timeout=5)
            assert (await client.post(f"/internal/v1/jobs/{job_id}/cancel", json={})).status_code == 200
            release.set()
            assert await task
            async with app.state.sessions() as session:
                job = await session.get(Job, job_id)
                assert job.status == "CANCELLED" and job.request_encrypted is None
                commands = (await session.execute(select(Command).where(Command.job_id == job_id))).scalars().all()
                assert len(commands) == 1 and commands[0].status == "CANCELLED"
            for _ in range(2):
                assert await process_cleanup(app.state.sessions, artifacts, job_id)
            async with app.state.sessions() as session:
                requests = (await session.execute(select(CleanupRequest)
                    .where(CleanupRequest.job_id == job_id))).scalars().all()
                assert len(requests) == 2 and all(request.done for request in requests)
    finally:
        release.set()
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_input_expiration_without_artifact_service():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            async with app.state.sessions.begin() as session:
                job = await session.get(Job, job_id)
                job.input_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            assert await process_expirations(app.state.sessions, job_id)
            async with app.state.sessions() as session:
                job = await session.get(Job, job_id)
                assert job.status == "FAILED" and job.error_code == "INPUT_EXPIRED"
                assert job.request_encrypted is None
            assert not await process_cleanup(app.state.sessions, None, job_id)
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_failed_file_attempt_uses_new_output_and_queues_old_for_deletion():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()

    def worker(request):
        body = json.loads(request.content)
        if request.url.path == "/v1/validate":
            return httpx.Response(200, json={"request_id": body["request_id"],
                                             "decision": "ACCEPTED", "reasons": [],
                                             "model_version": "model-1",
                                             "model_versions": {"person_detection": "1", "pose_estimation": "1"}})
        if request.url.path == "/v1/compare":
            return httpx.Response(200, json={"request_id": body["request_id"],
                                             "decision": "SAME_PERSON",
                                             "model_versions": {"face_detector": "1", "face_recognizer": "1"}})
        return httpx.Response(503, json={"code": "MODEL_UNAVAILABLE", "retryable": True})

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=httpx.MockTransport(worker)) as worker_client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            for _ in range(4):
                await dispatch_one(app.state.sessions, app.state.cipher, {
                    "FACE_VALIDATION": "https://worker.test", "BODY_VALIDATION": "https://worker.test",
                    "IDENTITY_VERIFICATION": "https://worker.test", "NORMALIZE_FACE": "https://worker.test",
                }, artifacts, worker_client, job_id)
            async with app.state.sessions() as session:
                commands = (await session.execute(select(Command).where(Command.job_id == job_id,
                    Command.stage == "NORMALIZE_FACE").order_by(Command.attempt))).scalars().all()
                assert len(commands) == 2 and commands[0].attempt == 1 and commands[1].attempt == 2
                old_output = app.state.cipher.decrypt(commands[0].payload_encrypted)["output_artifact_id"]
                new_output = app.state.cipher.decrypt(commands[1].payload_encrypted)["output_artifact_id"]
                assert old_output != new_output
                assert await session.get(CleanupRequest, old_output)
                assert (await session.get(Job, job_id)).failed_attempt_count == 1
    finally:
        await app.state.engine.dispose()
