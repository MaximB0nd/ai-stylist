import hashlib
import json
import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import Cipher
from app.db import Artifact, Command, Event, ImageSlot, Job, OutfitReservation, utcnow
from app.errors import AppError
from app.jobs import artifact_id, event_for, queue_cleanup, scrub_sensitive
from app.schemas import WorkerResult

RETRY_DELAYS = (5, 30, 120)


async def make_command(session: AsyncSession, cipher: Cipher, job: Job, stage: str,
                       payload: dict, order_index: int | None = None, attempt: int = 1,
                       delay: int = 0) -> Command:
    command = Command(id=str(uuid4()), job_id=job.id, stage=stage, attempt=attempt,
                      order_index=order_index, payload_encrypted=cipher.encrypt(payload),
                      status="PENDING", next_send_at=utcnow() + timedelta(seconds=delay))
    session.add(command)
    return command


async def artifact(session: AsyncSession, job: Job, kind: str, index: int | None = None) -> Artifact:
    value = Artifact(id=artifact_id(), job_id=job.id, kind=kind, order_index=index)
    session.add(value)
    return value


async def seed_preparation(session: AsyncSession, cipher: Cipher, job: Job) -> None:
    face = await artifact(session, job, "PREPARED_FACE")
    body = await artifact(session, job, "PREPARED_BODY")
    await make_command(session, cipher, job, "PREPARATION", {
        "face_artifact_id": job.face_artifact_id, "body_artifact_id": job.body_artifact_id,
        "prepared_face_artifact_id": face.id, "prepared_body_artifact_id": body.id,
    })


async def selected_artifact(session: AsyncSession, job: Job, kind: str) -> Artifact:
    value = (await session.execute(select(Artifact).where(Artifact.job_id == job.id, Artifact.kind == kind))).scalar_one_or_none()
    if value is None:
        raise AppError(409, "MISSING_ARTIFACT", "Expected artifact is absent")
    return value


async def seed_styling(session: AsyncSession, cipher: Cipher, job: Job) -> None:
    slot = await session.get(ImageSlot, (job.id, job.current_index))
    request = cipher.decrypt(job.request_encrypted)
    hashes = (await session.execute(select(OutfitReservation.outfit_hash).where(OutfitReservation.job_id == job.id))).scalars().all()
    await make_command(session, cipher, job, "STYLING", {
        "person": request["person"], "preferences": request["preferences"],
        "reserved_outfit_hashes": sorted(hashes),
    }, slot.order_index)


async def seed_generation(session: AsyncSession, cipher: Cipher, job: Job,
                          slot: ImageSlot, candidate_id: str | None = None,
                          attempt: int = 1, delay: int = 0) -> None:
    if candidate_id is None:
        candidate = await artifact(session, job, "CANDIDATE", slot.order_index)
        candidate_id = candidate.id
        slot.candidate_count += 1
        slot.candidate_artifact_id = candidate_id
    face = await selected_artifact(session, job, "PREPARED_FACE")
    body = await selected_artifact(session, job, "PREPARED_BODY")
    outfit = cipher.decrypt(slot.outfit_encrypted)
    await make_command(session, cipher, job, "GENERATION", {
        "prepared_face_artifact_id": face.id, "prepared_body_artifact_id": body.id,
        "outfit_spec_version": outfit["outfit_spec_version"], "outfit_spec": outfit["outfit_spec"],
        "seed": secrets.randbelow(2**32), "candidate_artifact_id": candidate_id,
    }, slot.order_index, attempt, delay)


async def seed_verification(session: AsyncSession, cipher: Cipher, job: Job,
                            slot: ImageSlot, attempt: int = 1, delay: int = 0) -> None:
    outfit = cipher.decrypt(slot.outfit_encrypted)
    await make_command(session, cipher, job, "VERIFICATION", {
        "face_artifact_id": job.face_artifact_id, "body_artifact_id": job.body_artifact_id,
        "candidate_artifact_id": slot.candidate_artifact_id,
        "outfit_spec_version": outfit["outfit_spec_version"], "outfit_spec": outfit["outfit_spec"],
    }, slot.order_index, attempt, delay)


async def fail_job(session: AsyncSession, job: Job, code: str) -> None:
    now = utcnow()
    job.status, job.stage = "FAILED", "DONE"
    job.error_code, job.error_message = code, "Processing failed"
    job.request_encrypted = None
    job.updated_at = now
    await scrub_sensitive(session, job)
    await queue_cleanup(session, job, now)
    session.add(event_for(job, now))


def store_artifact(value: Artifact, result: dict) -> None:
    if result.get("artifact_id") != value.id:
        raise AppError(409, "ARTIFACT_ID_MISMATCH", "Unexpected artifact result")
    value.checksum_sha256 = result["checksum_sha256"]
    value.size_bytes = result["size_bytes"]
    value.format = result["format"]
    value.width = result["width"]
    value.height = result["height"]


def validate_result(command: Command, body: WorkerResult, cipher: Cipher) -> None:
    if body.status != "SUCCEEDED":
        return
    result = body.result
    payload = cipher.decrypt(command.payload_encrypted)
    try:
        if command.stage == "PREPARATION":
            for side in ("face", "body"):
                value = result[f"prepared_{side}"]
                if value["artifact_id"] != payload[f"prepared_{side}_artifact_id"]:
                    raise ValueError("Artifact mismatch")
                _validate_image(value)
        elif command.stage == "STYLING":
            if not isinstance(result["outfit_spec"], dict) or not result["outfit_spec"]:
                raise ValueError("Empty outfit")
            if not isinstance(result["outfit_spec_version"], str) or not result["outfit_spec_version"]:
                raise ValueError("Missing outfit version")
        elif command.stage == "GENERATION":
            if result["artifact_id"] != payload["candidate_artifact_id"] or result["seed"] != payload["seed"]:
                raise ValueError("Candidate mismatch")
            _validate_image(result)
            if not result["model_version"] or not result["prompt_version"]:
                raise ValueError("Missing version")
        elif command.stage == "VERIFICATION":
            if result["verdict"] not in ("ACCEPTED", "REJECTED", "INCONCLUSIVE"):
                raise ValueError("Invalid verdict")
            if not isinstance(result["reason_codes"], list) or not result["policy_version"]:
                raise ValueError("Invalid verification metadata")
        elif command.stage == "NOTIFICATION":
            if result["event_id"] != payload["event_id"] or not 200 <= result["http_status"] < 300:
                raise ValueError("Invalid delivery receipt")
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(409, "INVALID_RESULT", "Worker result does not match contract") from exc


def _validate_image(value: dict) -> None:
    if (not isinstance(value["checksum_sha256"], str) or
            not isinstance(value["size_bytes"], int) or value["size_bytes"] <= 0 or
            not isinstance(value["format"], str) or not value["format"] or
            not isinstance(value["width"], int) or value["width"] <= 0 or
            not isinstance(value["height"], int) or value["height"] <= 0):
        raise ValueError("Invalid image metadata")


async def apply_result(session: AsyncSession, cipher: Cipher, job: Job,
                       command: Command, body: WorkerResult) -> None:
    stage, result = command.stage, body.result
    if stage == "NOTIFICATION":
        event_id = cipher.decrypt(command.payload_encrypted)["event_id"]
        event = await session.get(Event, event_id)
        if body.status == "SUCCEEDED":
            if result.get("event_id") != event_id or not 200 <= result.get("http_status", 0) < 300:
                raise AppError(409, "INVALID_RESULT", "Invalid notification receipt")
            event.delivery_status = "DELIVERED"
        elif body.error.retryable and command.attempt < 4:
            await make_command(session, cipher, job, stage, cipher.decrypt(command.payload_encrypted),
                               attempt=command.attempt + 1, delay=RETRY_DELAYS[command.attempt - 1])
        else:
            event.delivery_status = "UNDELIVERED"
        return

    if body.status == "FAILED":
        job.failed_attempt_count += 1
        if body.error.retryable and command.attempt < 4:
            await make_command(session, cipher, job, stage, cipher.decrypt(command.payload_encrypted),
                               command.order_index, command.attempt + 1, RETRY_DELAYS[command.attempt - 1])
        else:
            await fail_job(session, job, body.error.code)
        return

    if stage == "PREPARATION":
        payload = cipher.decrypt(command.payload_encrypted)
        for side in ("face", "body"):
            value = await session.get(Artifact, payload[f"prepared_{side}_artifact_id"])
            store_artifact(value, result[f"prepared_{side}"])
        job.stage = "STYLING"
        await seed_styling(session, cipher, job)
    elif stage == "STYLING":
        outfit = result.get("outfit_spec")
        version = result.get("outfit_spec_version")
        if not isinstance(outfit, dict) or not outfit or not isinstance(version, str) or not version:
            raise AppError(409, "INVALID_RESULT", "Invalid outfit")
        digest = hashlib.sha256(json.dumps({"outfit_spec_version": version, "outfit_spec": outfit},
                                        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        slot = await session.get(ImageSlot, (job.id, command.order_index))
        if await session.get(OutfitReservation, (job.id, digest)):
            job.failed_attempt_count += 1
            if command.attempt >= 4:
                await fail_job(session, job, "DUPLICATE_OUTFIT")
            else:
                payload = cipher.decrypt(command.payload_encrypted)
                payload["reserved_outfit_hashes"] = sorted(set(payload["reserved_outfit_hashes"] + [digest]))
                await make_command(session, cipher, job, stage, payload, command.order_index,
                                   command.attempt + 1, RETRY_DELAYS[command.attempt - 1])
            return
        session.add(OutfitReservation(job_id=job.id, outfit_hash=digest))
        slot.outfit_hash = digest
        slot.outfit_encrypted = cipher.encrypt({"outfit_spec_version": version, "outfit_spec": outfit})
        job.stage = "GENERATION"
        await seed_generation(session, cipher, job, slot)
    elif stage == "GENERATION":
        slot = await session.get(ImageSlot, (job.id, command.order_index))
        value = await session.get(Artifact, slot.candidate_artifact_id)
        store_artifact(value, result)
        value.result_metadata = {
            "model_version": result["model_version"], "prompt_version": result["prompt_version"],
            "outfit_spec_version": cipher.decrypt(slot.outfit_encrypted)["outfit_spec_version"],
            "seed": result["seed"],
        }
        job.stage = "VERIFICATION"
        await seed_verification(session, cipher, job, slot)
    elif stage == "VERIFICATION":
        slot = await session.get(ImageSlot, (job.id, command.order_index))
        verdict = result.get("verdict")
        if verdict == "INCONCLUSIVE":
            job.failed_attempt_count += 1
            if command.attempt >= 4:
                await fail_job(session, job, "VERIFICATION_INCONCLUSIVE")
            else:
                await seed_verification(session, cipher, job, slot, command.attempt + 1,
                                        RETRY_DELAYS[command.attempt - 1])
            return
        if verdict == "REJECTED":
            job.failed_attempt_count += 1
            if slot.candidate_count >= 3:
                await fail_job(session, job, "CANDIDATES_REJECTED")
            else:
                job.stage = "GENERATION"
                await seed_generation(session, cipher, job, slot)
            return
        if verdict != "ACCEPTED":
            raise AppError(409, "INVALID_RESULT", "Unknown verification verdict")
        slot.status, slot.accepted_artifact_id = "ACCEPTED", slot.candidate_artifact_id
        job.accepted_image_count += 1
        job.current_index += 1
        if job.current_index == job.requested_image_count:
            job.status, job.stage = "COMPLETED", "DONE"
            job.result_delivery_status = "AVAILABLE"
            job.results_available_until = utcnow() + timedelta(hours=24)
            job.request_encrypted = None
            for old_slot in (await session.execute(select(ImageSlot).where(ImageSlot.job_id == job.id))).scalars():
                old_slot.outfit_encrypted = None
        else:
            job.stage = "STYLING"
            await seed_styling(session, cipher, job)
        job.updated_at = utcnow()
        session.add(event_for(job, job.updated_at))
    job.updated_at = utcnow()
    if stage not in ("VERIFICATION",):
        session.add(event_for(job, job.updated_at))
