from datetime import timedelta

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.artifacts import ArtifactClient, ArtifactFailure
from app.crypto import Cipher
from app.db import CleanupRequest, Command, Event, Job, utcnow
from app.jobs import expire_results
from app.pipeline import fail_job, make_command


async def process_expirations(sessions: async_sessionmaker[AsyncSession]) -> bool:
    now = utcnow()
    async with sessions.begin() as session:
        job = (await session.execute(select(Job).where(
            ((Job.status.in_(("QUEUED", "PROCESSING"))) & (Job.deadline_at <= now)) |
            ((Job.stage == "IMPORT") & (Job.status.in_(("QUEUED", "PROCESSING"))) &
             (Job.input_expires_at <= now)) |
            ((Job.status == "COMPLETED") & (Job.result_delivery_status == "AVAILABLE") &
             (Job.results_available_until <= now))
        ).order_by(Job.created_at).limit(1).with_for_update(skip_locked=True))).scalar_one_or_none()
        if job is None:
            return False
        if job.status == "COMPLETED":
            await expire_results(session, job, now)
        else:
            code = "INPUT_EXPIRED" if job.stage == "IMPORT" and job.input_expires_at <= now else "JOB_EXPIRED"
            await fail_job(session, job, code)
            await session.execute(update(Command).where(Command.job_id == job.id,
                                                        Command.stage != "NOTIFICATION",
                                                        Command.status != "DONE").values(status="CANCELLED"))
    return True


async def process_events(sessions: async_sessionmaker[AsyncSession], cipher: Cipher,
                         job_id: str | None = None) -> bool:
    async with sessions.begin() as session:
        previous = aliased(Event)
        query = select(Event).where(
            Event.delivery_status == "PENDING",
            ~exists(select(previous.id).where(previous.job_id == Event.job_id,
                                              previous.sequence < Event.sequence,
                                              previous.delivery_status.in_(("PENDING", "QUEUED"))))
        )
        if job_id is not None:
            query = query.where(Event.job_id == job_id)
        event = (await session.execute(query
                                       .order_by(Event.created_at).limit(1)
                                       .with_for_update(skip_locked=True))).scalar_one_or_none()
        if event is None:
            return False
        job = await session.get(Job, event.job_id)
        await make_command(session, cipher, job, "NOTIFICATION", event.payload)
        event.delivery_status = "QUEUED"
    return True


async def process_cleanup(sessions: async_sessionmaker[AsyncSession],
                          artifacts: ArtifactClient | None, job_id: str | None = None) -> bool:
    if artifacts is None:
        return False
    now = utcnow()
    async with sessions.begin() as session:
        query = select(CleanupRequest).where(
            CleanupRequest.done.is_(False), CleanupRequest.next_try_at <= now
        )
        if job_id is not None:
            query = query.where(CleanupRequest.job_id == job_id)
        request = (await session.execute(query.order_by(CleanupRequest.next_try_at).limit(1)
            .with_for_update(skip_locked=True))).scalar_one_or_none()
        if request is None:
            return False
        request.attempts += 1
        request.next_try_at = now + timedelta(minutes=3)
        value = request.artifact_id
    try:
        await artifacts.delete(value)
    except ArtifactFailure:
        return True
    async with sessions.begin() as session:
        request = await session.get(CleanupRequest, value, with_for_update=True)
        request.done = True
    return True
