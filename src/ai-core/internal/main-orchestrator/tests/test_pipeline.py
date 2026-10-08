import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from app.artifacts import ImportResult
from app.db import Command, Event, Job
from app.dispatch import dispatch_one
from app.imports import process_one_import
from app.main import create_app
from app.runtime import process_events
from app.settings import Settings
from test_jobs_api import request_body

DATABASE_URL = os.getenv("ORCHESTRATOR_TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:55439/orchestrator_test")


class FakeArtifacts:
    def __init__(self):
        self.deleted = []

    async def import_file(self, artifact_id, source_url, source_expires_at):
        return ImportResult(artifact_id=artifact_id, checksum_sha256="sha256:" + "a" * 64,
                            size_bytes=100, format="jpeg", url="https://files.test/read",
                            expires_at=datetime.now(UTC) + timedelta(minutes=10))

    async def access(self, artifact_id, operation, content_type="image/webp"):
        return {"artifact_id": artifact_id, "url": f"https://files.test/{operation}/{artifact_id}",
                "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat()}

    async def delete(self, artifact_id):
        self.deleted.append(artifact_id)


def metadata(artifact_id):
    return {"artifact_id": artifact_id, "checksum_sha256": "sha256:" + "b" * 64,
            "size_bytes": 100, "format": "webp", "width": 512, "height": 768}


@pytest.mark.asyncio
async def test_full_pipeline_rejected_candidate_and_notification():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    app.state.artifacts = artifacts
    sent = []
    transport = httpx.MockTransport(lambda request: (sent.append(request) or httpx.Response(202)))
    worker_urls = {stage: "https://worker.test" for stage in ("PREPARATION", "STYLING", "GENERATION", "VERIFICATION", "NOTIFICATION")}

    async def command(stage, job_id, latest=True):
        async with app.state.sessions() as session:
            rows = (await session.execute(select(Command).where(Command.job_id == job_id, Command.stage == stage)
                                          .order_by(Command.created_at, Command.id))).scalars().all()
            return rows[-1] if latest else rows[0]

    async def callback(client, cmd, result=None, error=None):
        response = await client.post("/internal/v1/worker-results", json={
            "contract_version": 1, "message_id": str(uuid4()), "command_id": cmd.id,
            "job_id": cmd.job_id, "stage": cmd.stage, "attempt": cmd.attempt,
            "order_index": cmd.order_index, "status": "FAILED" if error else "SUCCEEDED",
            "result": result, "error": error,
        })
        assert response.status_code == 204, response.text

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=transport) as worker_client:
            created = await client.post("/internal/v1/jobs", json=request_body())
            assert created.status_code == 201
            job_id = created.json()["job_id"]
            assert await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            assert await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)

            prep = await command("PREPARATION", job_id)
            assert await dispatch_one(app.state.sessions, app.state.cipher, worker_urls, artifacts, worker_client, job_id)
            prep_payload = app.state.cipher.decrypt(prep.payload_encrypted)
            await callback(client, prep, {f"prepared_{side}": metadata(prep_payload[f"prepared_{side}_artifact_id"])
                                          for side in ("face", "body")})

            styling = await command("STYLING", job_id)
            await callback(client, styling, {"outfit_spec_version": "1.0", "outfit_spec": {"items": ["jacket"]},
                                             "model_version": "stylist-1", "prompt_version": "prompt-1"})
            generation = await command("GENERATION", job_id)
            first_payload = app.state.cipher.decrypt(generation.payload_encrypted)
            first_candidate = first_payload["candidate_artifact_id"]
            await callback(client, generation, {**metadata(first_candidate), "model_version": "gen-1",
                                                "prompt_version": "prompt-1", "seed": first_payload["seed"]})
            verification = await command("VERIFICATION", job_id)
            await callback(client, verification, {"verdict": "REJECTED", "reason_codes": ["QUALITY"], "policy_version": "1"})
            generation2 = await command("GENERATION", job_id)
            second_payload = app.state.cipher.decrypt(generation2.payload_encrypted)
            second_candidate = second_payload["candidate_artifact_id"]
            assert second_candidate != first_candidate
            await callback(client, generation2, {**metadata(second_candidate), "model_version": "gen-1",
                                                 "prompt_version": "prompt-1", "seed": second_payload["seed"]})
            verification2 = await command("VERIFICATION", job_id)
            await callback(client, verification2, {"verdict": "ACCEPTED", "reason_codes": [], "policy_version": "1"})
            got = await client.get(f"/internal/v1/jobs/{job_id}")
            assert got.status_code == 200, got.text
            view = got.json()
            assert view["status"] == "COMPLETED" and view["accepted_image_count"] == 1
            assert view["results"][0]["artifact_id"] == second_candidate
            assert view["results"][0]["download_url"].startswith("https://files.test/READ/")
            assert view["results"][0]["model_version"] == "gen-1"
            async with app.state.sessions() as session:
                assert (await session.get(Job, job_id)).request_encrypted is None
            assert await process_events(app.state.sessions, app.state.cipher, job_id)
            notification = await command("NOTIFICATION", job_id)
            payload = app.state.cipher.decrypt(notification.payload_encrypted)
            await callback(client, notification, {"event_id": payload["event_id"], "http_status": 204,
                                                  "delivered_at": datetime.now(UTC).isoformat()})
            async with app.state.sessions() as session:
                assert (await session.get(Event, payload["event_id"])).delivery_status == "DELIVERED"
            ack = await client.post(f"/internal/v1/jobs/{job_id}/results/ack", json={})
            assert ack.status_code == 204
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_callback_retry_and_duplicate_do_not_repeat_transition():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            async with app.state.sessions() as session:
                cmd = (await session.execute(select(Command).where(Command.job_id == job_id, Command.stage == "PREPARATION"))).scalar_one()
                payload = {"contract_version": 1, "message_id": str(uuid4()), "command_id": cmd.id,
                           "job_id": job_id, "stage": "PREPARATION", "attempt": 1, "order_index": None,
                           "status": "FAILED", "result": None,
                           "error": {"code": "TEMPORARY", "message": "Retry", "retryable": True}}
            assert (await client.post("/internal/v1/worker-results", json=payload)).status_code == 204
            assert (await client.post("/internal/v1/worker-results", json=payload)).status_code == 204
            async with app.state.sessions() as session:
                commands = (await session.execute(select(Command).where(Command.job_id == job_id, Command.stage == "PREPARATION"))).scalars().all()
                assert len(commands) == 2
                assert {cmd.attempt for cmd in commands} == {1, 2}
                assert (await session.get(Job, job_id)).failed_attempt_count == 1
    finally:
        await app.state.engine.dispose()
