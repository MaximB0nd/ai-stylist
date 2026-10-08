import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.artifacts import ArtifactFailure, ImportResult
from app.db import Artifact, CleanupRequest, Job
from app.imports import process_one_import
from app.main import create_app
from app.settings import Settings
from test_jobs_api import request_body


DATABASE_URL = os.getenv("ORCHESTRATOR_TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:55439/orchestrator_test")


class FakeArtifacts:
    def __init__(self, fail_body: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail_body = fail_body

    async def import_file(self, artifact_id: str, source_url: str, source_expires_at: datetime) -> ImportResult:
        self.calls.append((artifact_id, source_url))
        if self.fail_body and source_url.endswith("/body"):
            raise ArtifactFailure("SOURCE_UNAVAILABLE", True)
        return ImportResult(
            artifact_id=artifact_id, checksum_sha256="sha256:" + "a" * 64,
            size_bytes=100, format="jpeg", url="https://temporary-files.example/read-link",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )


@pytest.mark.asyncio
async def test_import_waits_for_service_then_copies_both_before_preparation() -> None:
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post("/internal/v1/jobs", json=request_body())
        assert created.status_code == 201
        job_id = created.json()["job_id"]
        assert not await process_one_import(app.state.sessions, app.state.cipher, None, job_id)
        async with app.state.sessions() as session:
            assert (await session.get(Job, job_id)).status == "QUEUED"

        fake = FakeArtifacts()
        assert await process_one_import(app.state.sessions, app.state.cipher, fake, job_id)
        async with app.state.sessions() as session:
            job = await session.get(Job, job_id)
            assert job.face_imported and not job.body_imported
            assert job.stage == "IMPORT"
        assert await process_one_import(app.state.sessions, app.state.cipher, fake, job_id)
        async with app.state.sessions() as session:
            job = await session.get(Job, job_id)
            assert job.status == "PROCESSING" and job.stage == "PREPARATION"
            assert job.face_imported and job.body_imported
            assert (await session.get(Artifact, job.face_artifact_id)).size_bytes == 100
        assert len(fake.calls) == 2 and fake.calls[0][1].endswith("/face") and fake.calls[1][1].endswith("/body")
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_partial_import_failure_keeps_cleanup_intents() -> None:
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post("/internal/v1/jobs", json=request_body())
        job_id = created.json()["job_id"]
        fake = FakeArtifacts(fail_body=True)
        assert await process_one_import(app.state.sessions, app.state.cipher, fake, job_id)
        for _ in range(4):
            assert await process_one_import(app.state.sessions, app.state.cipher, fake, job_id)
            async with app.state.sessions.begin() as session:
                job = await session.get(Job, job_id)
                job.import_next_at = datetime.now(UTC) - timedelta(seconds=1)
        async with app.state.sessions() as session:
            job = await session.get(Job, job_id)
            assert job.status == "FAILED" and job.request_encrypted is None
            assert await session.get(CleanupRequest, job.face_artifact_id) is not None
            assert await session.get(CleanupRequest, job.body_artifact_id) is not None
    finally:
        await app.state.engine.dispose()
