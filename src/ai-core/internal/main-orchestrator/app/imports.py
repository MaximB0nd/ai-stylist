from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts import ArtifactClient, ArtifactFailure, ImportResult
from app.crypto import Cipher
from app.db import Artifact, Job, utcnow
from app.jobs import event_for, queue_cleanup, scrub_sensitive
from app.pipeline import seed_preparation


RETRY_DELAYS = (5, 30, 120)


def public_import_error(code: str) -> str:
    if code in {"SOURCE_TOO_LARGE", "SOURCE_UNSUPPORTED_IMAGE_TYPE", "SOURCE_UNPROCESSABLE",
                "IMAGE_DIMENSIONS_EXCEEDED"}:
        return "PHOTO_UNPROCESSABLE"
    if code == "SOURCE_URL_NOT_ALLOWED":
        return "INPUT_URL_NOT_ALLOWED"
    if code in {"SOURCE_TIMEOUT", "SOURCE_UNAVAILABLE", "SOURCE_NOT_ACCESSIBLE",
                "IMPORT_IN_PROGRESS", "ARTIFACT_CONFLICT", "INVALID_ARTIFACT_RESPONSE"}:
        return "PREPROCESSING_UNAVAILABLE"
    return code


async def fail_import(session: AsyncSession, job: Job, code: str) -> None:
    now = utcnow()
    job.status = "FAILED"
    job.stage = "DONE"
    job.error_code = public_import_error(code)
    job.error_message = "Input import failed"
    job.request_encrypted = None
    job.updated_at = now
    await scrub_sensitive(session, job)
    await queue_cleanup(session, job, now)
    session.add(event_for(job, now))


async def process_one_import(
    sessions: async_sessionmaker[AsyncSession],
    cipher: Cipher,
    artifacts: ArtifactClient | None,
    job_id: str | None = None,
) -> bool:
    if artifacts is None:
        return False
    now = utcnow()
    async with sessions.begin() as session:
        query = select(Job).where(Job.stage == "IMPORT", Job.status.in_(("QUEUED", "PROCESSING")), Job.import_next_at <= now)
        if job_id is not None:
            query = query.where(Job.id == job_id)
        job = (await session.execute(
            query
            .order_by(Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if job is None:
            return False
        if now >= job.input_expires_at:
            await fail_import(session, job, "INPUT_EXPIRED")
            return True
        if now >= job.deadline_at:
            await fail_import(session, job, "JOB_EXPIRED")
            return True
        if job.status == "QUEUED":
            job.status = "PROCESSING"
            job.updated_at = now
            session.add(event_for(job, now))
        side = "face" if not job.face_imported else "body"
        artifact_id = job.face_artifact_id if side == "face" else job.body_artifact_id
        source = cipher.decrypt(job.request_encrypted)["inputs"][side]["url"]
        job.import_next_at = now + timedelta(minutes=3)
        selected_job_id = job.id

    try:
        result = await artifacts.import_file(artifact_id, source)
    except ArtifactFailure as exc:
        async with sessions.begin() as session:
            job = (await session.execute(select(Job).where(Job.id == selected_job_id).with_for_update())).scalar_one()
            if job.status in ("CANCELLED", "FAILED", "COMPLETED"):
                return True
            now = utcnow()
            if exc.code == "INPUT_EXPIRED" or now >= job.input_expires_at:
                await fail_import(session, job, "INPUT_EXPIRED")
            elif not exc.retryable:
                await fail_import(session, job, exc.code)
            elif exc.ambiguous:
                job.import_next_at = now + timedelta(seconds=5)
            elif exc.code == "IMPORT_IN_PROGRESS":
                job.import_next_at = now + timedelta(seconds=exc.retry_after_seconds or 5)
            else:
                job.import_attempt += 1
                job.failed_attempt_count += 1
                if job.import_attempt >= 4:
                    await fail_import(session, job, exc.code)
                else:
                    job.import_next_at = now + timedelta(seconds=max(
                        RETRY_DELAYS[job.import_attempt - 1], exc.retry_after_seconds or 0))
        return True

    async with sessions.begin() as session:
        job = (await session.execute(select(Job).where(Job.id == selected_job_id).with_for_update())).scalar_one()
        artifact = await session.get(Artifact, artifact_id)
        artifact.checksum_sha256 = result.checksum_sha256
        artifact.size_bytes = result.size_bytes
        artifact.format = result.media_type
        artifact.width = result.width
        artifact.height = result.height
        if job.status in ("CANCELLED", "FAILED", "COMPLETED"):
            await queue_cleanup(session, job, utcnow())
            return True
        if side == "face":
            job.face_imported = True
        else:
            job.body_imported = True
        job.import_attempt = 0
        job.import_next_at = utcnow()
        job.updated_at = utcnow()
        if job.face_imported and job.body_imported:
            job.stage = "FACE_VALIDATION"
            session.add(event_for(job, job.updated_at))
            await seed_preparation(session, cipher, job)
    return True
