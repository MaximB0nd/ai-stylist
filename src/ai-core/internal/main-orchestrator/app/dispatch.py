from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts import ArtifactClient, ArtifactFailure
from app.crypto import Cipher
from app.db import Command, Event, Job, utcnow
from app.pipeline import RETRY_DELAYS, make_command


async def hydrate(payload: dict, stage: str, artifacts: ArtifactClient | None) -> dict:
    if stage == "NOTIFICATION" or stage == "STYLING":
        return payload
    if artifacts is None:
        raise ArtifactFailure("ARTIFACT_SERVICE_UNAVAILABLE", True)

    async def url(key: str, operation: str) -> str:
        access = await artifacts.access(payload[key], operation)
        return access["url"]

    if stage == "PREPARATION":
        return {
            "face": {"artifact_id": payload["face_artifact_id"], "read_url": await url("face_artifact_id", "READ")},
            "body": {"artifact_id": payload["body_artifact_id"], "read_url": await url("body_artifact_id", "READ")},
            "prepared_face": {"artifact_id": payload["prepared_face_artifact_id"], "write_url": await url("prepared_face_artifact_id", "WRITE")},
            "prepared_body": {"artifact_id": payload["prepared_body_artifact_id"], "write_url": await url("prepared_body_artifact_id", "WRITE")},
        }
    if stage == "GENERATION":
        return {
            "prepared_face_read_url": await url("prepared_face_artifact_id", "READ"),
            "prepared_body_read_url": await url("prepared_body_artifact_id", "READ"),
            "outfit_spec_version": payload["outfit_spec_version"], "outfit_spec": payload["outfit_spec"],
            "seed": payload["seed"], "candidate_artifact_id": payload["candidate_artifact_id"],
            "write_url": await url("candidate_artifact_id", "WRITE"),
        }
    if stage == "VERIFICATION":
        return {
            "face_read_url": await url("face_artifact_id", "READ"),
            "body_read_url": await url("body_artifact_id", "READ"),
            "candidate_read_url": await url("candidate_artifact_id", "READ"),
            "outfit_spec_version": payload["outfit_spec_version"], "outfit_spec": payload["outfit_spec"],
        }
    raise ValueError(stage)


async def dispatch_one(sessions: async_sessionmaker[AsyncSession], cipher: Cipher,
                       worker_urls: dict[str, str], artifacts: ArtifactClient | None,
                       client: httpx.AsyncClient, job_id: str | None = None) -> bool:
    now = utcnow()
    async with sessions.begin() as session:
        query = select(Command).where(Command.status.in_(("PENDING", "AWAITING", "SENDING")),
                                      Command.next_send_at <= now)
        if job_id is not None:
            query = query.where(Command.job_id == job_id)
        command = (await session.execute(
            query
            .order_by(Command.next_send_at, Command.created_at).limit(1)
            .with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if command is None:
            return False
        job = await session.get(Job, command.job_id)
        if job.status in ("FAILED", "CANCELLED", "COMPLETED") and command.stage != "NOTIFICATION":
            command.status = "CANCELLED"
            return True
        if command.stage == "NOTIFICATION":
            event = await session.get(Event, cipher.decrypt(command.payload_encrypted)["event_id"])
            if now >= event.created_at + timedelta(hours=24):
                event.delivery_status = "UNDELIVERED"
                command.status = "CANCELLED"
                return True
        command.status = "SENDING"
        command.sent_count += 1
        command.next_send_at = now + timedelta(minutes=3)
        selected = (command.id, command.job_id, command.stage, command.attempt,
                    command.order_index, command.payload_encrypted)

    command_id, job_id, stage, attempt, index, encrypted = selected
    try:
        worker_url = worker_urls.get(stage)
        if not worker_url:
            raise RuntimeError("Worker not configured")
        payload = await hydrate(cipher.decrypt(encrypted), stage, artifacts)
        response = await client.post(f"{worker_url.rstrip('/')}/internal/v1/commands", json={
            "contract_version": 1, "command_id": command_id, "job_id": job_id,
            "stage": stage, "attempt": attempt, "order_index": index, "payload": payload,
        })
        accepted = response.status_code == 202
    except (httpx.HTTPError, ArtifactFailure, RuntimeError, KeyError, ValueError):
        accepted = False
    async with sessions.begin() as session:
        command = (await session.execute(select(Command).where(Command.id == command_id).with_for_update())).scalar_one()
        if command.status == "SENDING":
            if stage == "NOTIFICATION" and not accepted:
                event = await session.get(Event, cipher.decrypt(encrypted)["event_id"])
                command.status = "DONE"
                if attempt >= 4:
                    event.delivery_status = "UNDELIVERED"
                else:
                    job = await session.get(Job, job_id)
                    await make_command(session, cipher, job, stage, cipher.decrypt(encrypted),
                                       attempt=attempt + 1, delay=RETRY_DELAYS[attempt - 1])
                return True
            command.status = "AWAITING" if accepted else "PENDING"
            command.accepted_at = utcnow() if accepted else command.accepted_at
            command.next_send_at = utcnow() + timedelta(minutes=30 if accepted else 1)
    return True
