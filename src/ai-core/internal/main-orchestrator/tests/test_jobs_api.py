import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.db import CleanupRequest, Job
from app.main import create_app
from app.schemas import JobCreate
from app.settings import Settings


DATABASE_URL = os.getenv("ORCHESTRATOR_TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:55439/orchestrator_test")


def request_body() -> dict:
    body = {
        "idempotency_key_hash": uuid4().hex.ljust(64, "0"),
        "request_hash": "0" * 64,
        "requested_image_count": 1,
        "inputs": {
            "face_photo_url": "https://files.example/face",
            "body_photo_url": "https://files.example/body",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
        "person": {"age": 26, "height_cm": 172, "gender": "female"},
        "preferences": {"occasion": "office", "styles": ["classic"], "shoes": ["loafers"], "impressions": ["confident"], "description": "Office look"},
    }
    body["request_hash"] = JobCreate.model_validate(body).computed_hash()
    return body


@pytest.fixture
def app():
    application = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    yield application


@pytest.mark.asyncio
async def test_create_idempotency_conflict_and_cancel(app) -> None:
    body = request_body()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/internal/v1/jobs", json=body)
        assert first.status_code == 201
        job_id = first.json()["job_id"]
        assert first.json()["status"] == "QUEUED"
        assert (await client.post("/internal/v1/jobs", json=body)).status_code == 200

        changed = dict(body)
        changed["requested_image_count"] = 2
        changed["request_hash"] = JobCreate.model_validate(changed).computed_hash()
        conflict = await client.post("/internal/v1/jobs", json=changed)
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

        assert (await client.get(f"/internal/v1/jobs/{job_id}")).status_code == 200
        cancelled = await client.post(f"/internal/v1/jobs/{job_id}/cancel", json={})
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
        assert (await client.post(f"/internal/v1/jobs/{job_id}/cancel", json={})).json()["status"] == "CANCELLED"
        assert (await client.post(f"/internal/v1/jobs/{job_id}/results/ack", json={})).status_code == 409
        assert (await client.get(f"/internal/v1/jobs/{uuid4()}")).status_code == 404
    await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_ack_expiration_commits_state_and_cleanup(app) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/internal/v1/jobs", json=request_body())
        assert created.status_code == 201
        job_id = created.json()["job_id"]
        async with app.state.sessions.begin() as session:
            job = await session.get(Job, job_id)
            job.status = "COMPLETED"
            job.stage = "DONE"
            job.accepted_image_count = 1
            job.result_delivery_status = "AVAILABLE"
            job.results_available_until = datetime.now(UTC) - timedelta(seconds=1)
            job.request_encrypted = None

        late = await client.post(f"/internal/v1/jobs/{job_id}/results/ack", json={})
        assert late.status_code == 409 and late.json()["code"] == "RESULTS_EXPIRED"
        async with app.state.sessions() as session:
            job = await session.get(Job, job_id)
            assert job.result_delivery_status == "EXPIRED"
            assert await session.get(CleanupRequest, job.face_artifact_id) is not None
        assert (await client.post(f"/internal/v1/jobs/{job_id}/cancel", json={})).status_code == 409
    await app.state.engine.dispose()
