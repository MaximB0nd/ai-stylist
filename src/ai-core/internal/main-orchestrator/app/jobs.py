from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crypto import Cipher
from app.artifacts import ArtifactClient, ArtifactFailure
from app.db import Artifact, CleanupRequest, Command, Event, ImageSlot, Job, utcnow
from app.errors import AppError
from app.schemas import JobCreate


def artifact_id() -> str:
    return uuid4().hex


def event_for(job: Job, now: datetime) -> Event:
    job.sequence += 1
    event_id = str(uuid4())
    return Event(
        id=event_id, job_id=job.id, sequence=job.sequence,
        payload={
            "event_id": event_id, "job_id": job.id, "sequence": job.sequence,
            "status": job.status,
            "progress": {"requested_image_count": job.requested_image_count, "accepted_image_count": job.accepted_image_count},
            "occurred_at": now.isoformat().replace("+00:00", "Z"),
            "error": None if not job.error_code else {"code": job.error_code, "message": job.error_message, "retryable": False},
        },
        delivery_status="PENDING", created_at=now,
    )


async def create_job(
    sessions: async_sessionmaker[AsyncSession], cipher: Cipher, body: JobCreate,
) -> tuple[str, bool]:
    if body.computed_hash() != body.request_hash:
        raise AppError(400, "INVALID_REQUEST", "Request hash does not match body")
    now = utcnow()

    async def existing() -> tuple[str, bool] | None:
        async with sessions() as session:
            job = (await session.execute(select(Job).where(Job.idempotency_key_hash == body.idempotency_key_hash))).scalar_one_or_none()
            if job is None:
                return None
            if job.request_hash != body.request_hash:
                raise AppError(409, "IDEMPOTENCY_CONFLICT", "Key used with a different request")
            return job.id, False

    prior = await existing()
    if prior:
        return prior
    if body.inputs.expires_at < now + timedelta(minutes=30):
        raise AppError(400, "INVALID_REQUEST", "Input URLs expire too soon")
    job_id = str(uuid4())
    face_id, body_id = artifact_id(), artifact_id()
    try:
        async with sessions.begin() as session:
            job = Job(
                id=job_id,
                idempotency_key_hash=body.idempotency_key_hash,
                request_hash=body.request_hash,
                request_encrypted=cipher.encrypt(body.normalized_body()),
                status="QUEUED", stage="IMPORT",
                requested_image_count=body.requested_image_count,
                accepted_image_count=0, failed_attempt_count=0, current_index=0,
                input_expires_at=body.inputs.expires_at,
                deadline_at=now + timedelta(hours=24),
                face_artifact_id=face_id, body_artifact_id=body_id,
                face_imported=False, body_imported=False,
                import_attempt=0, import_next_at=now,
                sequence=0, created_at=now, updated_at=now,
            )
            session.add(job)
            await session.flush()
            session.add_all([
                Artifact(id=face_id, job_id=job_id, kind="INPUT_FACE", created_at=now),
                Artifact(id=body_id, job_id=job_id, kind="INPUT_BODY", created_at=now),
            ])
            session.add_all([
                ImageSlot(job_id=job_id, order_index=index, status="PENDING", candidate_count=0, stage_attempt=0)
                for index in range(body.requested_image_count)
            ])
            session.add(event_for(job, now))
        return job_id, True
    except IntegrityError:
        prior = await existing()
        if prior:
            return prior
        raise


async def locked_job(session: AsyncSession, job_id: str) -> Job:
    job = (await session.execute(select(Job).where(Job.id == job_id).with_for_update())).scalar_one_or_none()
    if job is None:
        raise AppError(404, "JOB_NOT_FOUND", "Job not found")
    return job


async def queue_cleanup(session: AsyncSession, job: Job, now: datetime) -> None:
    artifact_ids = (await session.execute(select(Artifact.id).where(Artifact.job_id == job.id))).scalars().all()
    existing = set((await session.execute(select(CleanupRequest.artifact_id).where(CleanupRequest.job_id == job.id))).scalars().all())
    session.add_all([
        CleanupRequest(artifact_id=value, job_id=job.id, done=False, attempts=0, next_try_at=now)
        for value in artifact_ids if value not in existing
    ])


async def scrub_sensitive(session: AsyncSession, job: Job) -> None:
    job.request_encrypted = None
    await session.execute(update(ImageSlot).where(ImageSlot.job_id == job.id).values(outfit_encrypted=None))
    await session.execute(update(Command).where(Command.job_id == job.id,
                                                Command.stage != "NOTIFICATION")
                          .values(payload_encrypted="", result_encrypted=None))


async def expire_results(session: AsyncSession, job: Job, now: datetime) -> None:
    if job.status == "COMPLETED" and job.result_delivery_status == "AVAILABLE" and job.results_available_until and now >= job.results_available_until:
        job.result_delivery_status = "EXPIRED"
        job.updated_at = now
        await queue_cleanup(session, job, now)


async def get_job(sessions: async_sessionmaker[AsyncSession], job_id: str,
                  artifacts: ArtifactClient | None = None) -> dict:
    async with sessions.begin() as session:
        job = await locked_job(session, job_id)
        await expire_results(session, job, utcnow())
        view = await public_view(session, job)
    if view["status"] == "COMPLETED" and view["result_delivery_status"] == "AVAILABLE":
        if artifacts is None:
            raise AppError(503, "ARTIFACT_SERVICE_UNAVAILABLE", "Result links unavailable", True)
        for result in view["results"]:
            try:
                access = await artifacts.access(result["artifact_id"], "READ")
            except ArtifactFailure as exc:
                raise AppError(503, exc.code, "Result links unavailable", True) from exc
            result["download_url"] = access["url"]
            result["download_url_expires_at"] = access["expires_at"]
    return view


async def cancel_job(sessions: async_sessionmaker[AsyncSession], job_id: str) -> dict:
    async with sessions.begin() as session:
        job = await locked_job(session, job_id)
        if job.status == "CANCELLED":
            return await public_view(session, job)
        if job.status not in {"QUEUED", "PROCESSING"}:
            raise AppError(409, "INVALID_JOB_STATE", "Job cannot be cancelled")
        now = utcnow()
        job.status, job.stage = "CANCELLED", "DONE"
        job.updated_at = now
        await session.execute(update(Command).where(Command.job_id == job.id,
                                                    Command.stage != "NOTIFICATION",
                                                    Command.status != "DONE").values(status="CANCELLED"))
        await scrub_sensitive(session, job)
        await queue_cleanup(session, job, now)
        session.add(event_for(job, now))
        return await public_view(session, job)


async def ack_results(sessions: async_sessionmaker[AsyncSession], job_id: str) -> None:
    expired = False
    async with sessions.begin() as session:
        job = await locked_job(session, job_id)
        now = utcnow()
        await expire_results(session, job, now)
        if job.status != "COMPLETED":
            raise AppError(409, "INVALID_JOB_STATE", "Results are not complete")
        if job.result_delivery_status == "EXPIRED":
            expired = True
        elif job.result_delivery_status == "AVAILABLE":
            job.result_delivery_status = "ACKNOWLEDGED"
            job.updated_at = now
            await queue_cleanup(session, job, now)
    if expired:
        raise AppError(409, "RESULTS_EXPIRED", "Results expired")


async def public_view(session: AsyncSession, job: Job) -> dict:
    result: dict = {
        "job_id": job.id,
        "status": job.status,
        "requested_image_count": job.requested_image_count,
        "accepted_image_count": job.accepted_image_count,
        "failed_attempt_count": job.failed_attempt_count,
        "updated_at": job.updated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "error": None if not job.error_code else {"code": job.error_code, "message": job.error_message, "retryable": False},
    }
    if job.status == "COMPLETED":
        result["result_delivery_status"] = job.result_delivery_status
        result["results_available_until"] = job.results_available_until.astimezone(UTC).isoformat().replace("+00:00", "Z")
        result["results"] = []
        if job.result_delivery_status == "AVAILABLE":
            slots = (await session.execute(select(ImageSlot).where(ImageSlot.job_id == job.id).order_by(ImageSlot.order_index))).scalars().all()
            for slot in slots:
                artifact = await session.get(Artifact, slot.accepted_artifact_id)
                result["results"].append({
                    "order_index": slot.order_index, "artifact_id": artifact.id,
                    "checksum_sha256": artifact.checksum_sha256, "size_bytes": artifact.size_bytes,
                    "format": artifact.format, "width": artifact.width, "height": artifact.height,
                    **(artifact.result_metadata or {}),
                })
    return result
