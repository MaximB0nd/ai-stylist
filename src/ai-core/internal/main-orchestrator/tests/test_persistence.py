import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.crypto import Cipher
from app.db import Artifact, CleanupRequest, Command, ImageSlot, Job, session_factory


TEST_DATABASE_URL = os.getenv(
    "ORCHESTRATOR_TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:55439/orchestrator_test",
)


@pytest.mark.asyncio
async def test_job_and_pending_work_survive_new_session() -> None:
    cipher = Cipher(Fernet.generate_key().decode())
    encrypted = cipher.encrypt({"inputs": {"face_photo_url": "https://files.example/secret"}})
    assert "files.example" not in encrypted
    job_id = str(uuid4())
    artifact_id = uuid4().hex
    command_id = str(uuid4())
    now = datetime.now(UTC)
    engine, sessions = session_factory(TEST_DATABASE_URL)
    try:
        async with sessions.begin() as session:
            session.add(Job(
                id=job_id,
                idempotency_key_hash=uuid4().hex.ljust(64, "0"),
                request_hash="a" * 64,
                request_encrypted=encrypted,
                status="QUEUED",
                stage="IMPORT",
                requested_image_count=1,
                accepted_image_count=0,
                failed_attempt_count=0,
                current_index=0,
                input_expires_at=now + timedelta(hours=1),
                deadline_at=now + timedelta(hours=24),
                face_artifact_id=artifact_id,
                body_artifact_id=uuid4().hex,
                face_imported=False,
                body_imported=False,
                import_attempt=0,
                import_next_at=now,
                sequence=0,
                created_at=now,
                updated_at=now,
            ))
            await session.flush()
            session.add(ImageSlot(job_id=job_id, order_index=0, status="PENDING", candidate_count=0, stage_attempt=0))
            session.add(Artifact(id=artifact_id, job_id=job_id, kind="INPUT_FACE", created_at=now))
            await session.flush()
            session.add(Command(
                id=command_id, job_id=job_id, stage="FACE_VALIDATION", attempt=1,
                payload_encrypted=cipher.encrypt({"image_artifact_id": artifact_id}),
                status="PENDING", next_send_at=now, sent_count=0, created_at=now,
            ))
            session.add(CleanupRequest(artifact_id=artifact_id, job_id=job_id, done=False, attempts=0, next_try_at=now))

        async with sessions() as session:
            job = await session.get(Job, job_id)
            command = await session.get(Command, command_id)
            pending = (await session.execute(select(CleanupRequest).where(CleanupRequest.job_id == job_id))).scalar_one()
            assert job is not None and cipher.decrypt(job.request_encrypted)["inputs"]["face_photo_url"].endswith("secret")
            assert command is not None and command.status == "PENDING"
            assert pending.artifact_id == artifact_id and not pending.done
    finally:
        await engine.dispose()
