import hashlib
import json
import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import Cipher
from app.db import Artifact, Command, ImageSlot, Job, OutfitReservation, utcnow
from app.errors import AppError
from app.jobs import artifact_id, event_for, queue_artifact_cleanup, queue_cleanup, scrub_sensitive

RETRY_DELAYS = (5, 30, 120)
FILE_OUTPUT_STAGES = {"NORMALIZE_FACE", "NORMALIZE_BODY", "GENERATION"}


async def make_command(session: AsyncSession, cipher: Cipher, job: Job, stage: str,
                       payload: dict, order_index: int | None = None, attempt: int = 1,
                       delay: int = 0) -> Command:
    command = Command(id=str(uuid4()), job_id=job.id, stage=stage, attempt=attempt,
                      order_index=order_index, payload_encrypted=cipher.encrypt(payload),
                      status="PENDING", next_send_at=utcnow() + timedelta(seconds=delay))
    session.add(command)
    return command


async def create_artifact(session: AsyncSession, job: Job, kind: str,
                          order_index: int | None = None) -> Artifact:
    value = Artifact(id=artifact_id(), job_id=job.id, kind=kind, order_index=order_index)
    session.add(value)
    return value


async def artifact_of_kind(session: AsyncSession, job: Job, kind: str) -> Artifact:
    value = (await session.execute(select(Artifact).where(Artifact.job_id == job.id,
                                                         Artifact.kind == kind)
                                   .order_by(Artifact.created_at.desc()))).scalars().first()
    if value is None:
        raise AppError(409, "MISSING_ARTIFACT", "Expected artifact is absent")
    return value


async def seed_preparation(session: AsyncSession, cipher: Cipher, job: Job) -> None:
    await make_command(session, cipher, job, "FACE_VALIDATION", {"image_artifact_id": job.face_artifact_id})


async def seed_styling(session: AsyncSession, cipher: Cipher, job: Job) -> None:
    request = cipher.decrypt(job.request_encrypted)
    hashes = (await session.execute(select(OutfitReservation.outfit_hash)
                                    .where(OutfitReservation.job_id == job.id))).scalars().all()
    await make_command(session, cipher, job, "STYLING", {
        "person": request["person"], "preferences": request["preferences"],
        "color_type": job.color_type, "reserved_outfit_hashes": sorted(hashes),
    }, job.current_index)


async def seed_generation(session: AsyncSession, cipher: Cipher, job: Job,
                          slot: ImageSlot) -> None:
    candidate = await create_artifact(session, job, "CANDIDATE", slot.order_index)
    slot.candidate_count += 1
    slot.candidate_artifact_id = candidate.id
    face = await artifact_of_kind(session, job, "PREPARED_FACE")
    body = await artifact_of_kind(session, job, "PREPARED_BODY")
    outfit = cipher.decrypt(slot.outfit_encrypted)
    await make_command(session, cipher, job, "GENERATION", {
        "face_artifact_id": face.id, "body_artifact_id": body.id,
        "outfit_spec_version": outfit["outfit_spec_version"], "outfit_spec": outfit["outfit_spec"],
        "seed": secrets.randbelow(2**32), "output_artifact_id": candidate.id,
    }, slot.order_index)


async def seed_verification(session: AsyncSession, cipher: Cipher, job: Job,
                            slot: ImageSlot, attempt: int = 1, delay: int = 0) -> None:
    outfit = cipher.decrypt(slot.outfit_encrypted)
    await make_command(session, cipher, job, "VERIFICATION", {
        "face_artifact_id": job.face_artifact_id, "body_artifact_id": job.body_artifact_id,
        "candidate_artifact_id": slot.candidate_artifact_id,
        "outfit_spec_version": outfit["outfit_spec_version"], "outfit_spec": outfit["outfit_spec"],
    }, slot.order_index, attempt, delay)


async def fail_job(session: AsyncSession, job: Job, code: str,
                   reasons: list[str] | None = None) -> None:
    now = utcnow()
    job.status, job.stage = "FAILED", "DONE"
    job.error_code, job.error_message = code, "Processing failed"
    job.error_reasons = sorted(set(reasons)) if reasons is not None else None
    job.updated_at = now
    await scrub_sensitive(session, job)
    await queue_cleanup(session, job, now)
    session.add(event_for(job, now))


def store_artifact(value: Artifact, result: dict) -> None:
    if not isinstance(result, dict):
        raise AppError(409, "INVALID_RESULT", "Missing artifact metadata")
    try:
        checksum, media_type = result["checksum_sha256"], result["media_type"]
        size, width, height = result["size_bytes"], result["width"], result["height"]
    except KeyError as exc:
        raise AppError(409, "INVALID_RESULT", "Missing artifact metadata") from exc
    if not (isinstance(checksum, str) and checksum.startswith("sha256:") and
            isinstance(media_type, str) and media_type.startswith("image/") and
            isinstance(size, int) and size > 0 and isinstance(width, int) and width > 0 and
            isinstance(height, int) and height > 0):
        raise AppError(409, "INVALID_RESULT", "Invalid artifact metadata")
    value.checksum_sha256, value.format, value.size_bytes = checksum, media_type, size
    value.width, value.height = width, height


async def retry_command(session: AsyncSession, cipher: Cipher, job: Job,
                        command: Command, code: str, retryable: bool,
                        public_code: str | None = None, duplicate_hash: str | None = None) -> None:
    job.failed_attempt_count += 1
    if not retryable or command.attempt >= 4:
        await fail_job(session, job, public_code or code)
        return
    payload = cipher.decrypt(command.payload_encrypted)
    if duplicate_hash is not None:
        payload["reserved_outfit_hashes"] = sorted(set(payload["reserved_outfit_hashes"] + [duplicate_hash]))
    if command.stage in FILE_OUTPUT_STAGES:
        await queue_artifact_cleanup(session, job, payload["output_artifact_id"], utcnow())
        kind = "CANDIDATE" if command.stage == "GENERATION" else (
            "PREPARED_FACE" if command.stage == "NORMALIZE_FACE" else "PREPARED_BODY")
        replacement = await create_artifact(session, job, kind, command.order_index)
        payload["output_artifact_id"] = replacement.id
        if command.stage == "GENERATION":
            slot = await session.get(ImageSlot, (job.id, command.order_index))
            slot.candidate_artifact_id = replacement.id
    await make_command(session, cipher, job, command.stage, payload, command.order_index,
                       command.attempt + 1, RETRY_DELAYS[command.attempt - 1])


async def apply_success(session: AsyncSession, cipher: Cipher, job: Job,
                        command: Command, result: dict) -> None:
    if result.get("request_id") != command.id:
        raise AppError(409, "INVALID_RESULT", "Mismatched request ID")
    stage = command.stage
    if stage in ("FACE_VALIDATION", "BODY_VALIDATION"):
        decision, reasons = result.get("decision"), result.get("reasons")
        if (decision not in ("ACCEPTED", "REJECTED") or not isinstance(reasons, list) or
                (decision == "ACCEPTED" and reasons) or
                (decision == "REJECTED" and not reasons) or
                any(not isinstance(reason, str) for reason in reasons)):
            raise AppError(409, "INVALID_RESULT", "Invalid photo decision")
        if stage == "FACE_VALIDATION" and not result.get("model_version"):
            raise AppError(409, "INVALID_RESULT", "Missing model version")
        if stage == "BODY_VALIDATION" and not result.get("model_versions"):
            raise AppError(409, "INVALID_RESULT", "Missing model versions")
        if decision == "REJECTED":
            await fail_job(session, job, "FACE_PHOTO_REJECTED" if stage == "FACE_VALIDATION" else "BODY_PHOTO_REJECTED", reasons)
            return
        next_stage = "BODY_VALIDATION" if stage == "FACE_VALIDATION" else "IDENTITY_VERIFICATION"
        job.stage = next_stage
        payload = {"image_artifact_id": job.body_artifact_id} if stage == "FACE_VALIDATION" else {
            "face_artifact_id": job.face_artifact_id, "body_artifact_id": job.body_artifact_id}
        await make_command(session, cipher, job, next_stage, payload)
    elif stage == "IDENTITY_VERIFICATION":
        if not result.get("model_versions"):
            raise AppError(409, "INVALID_RESULT", "Missing model versions")
        if result.get("decision") == "DIFFERENT_PERSON":
            await fail_job(session, job, "IDENTITY_MISMATCH")
            return
        if result.get("decision") != "SAME_PERSON":
            raise AppError(409, "INVALID_RESULT", "Invalid identity decision")
        job.stage = "NORMALIZE_FACE"
        output = await create_artifact(session, job, "PREPARED_FACE")
        await make_command(session, cipher, job, "NORMALIZE_FACE", {
            "image_artifact_id": job.face_artifact_id, "output_artifact_id": output.id,
            "profile": "face", "width": 512, "height": 512,
        })
    elif stage in ("NORMALIZE_FACE", "NORMALIZE_BODY"):
        payload = cipher.decrypt(command.payload_encrypted)
        output = await session.get(Artifact, payload["output_artifact_id"])
        store_artifact(output, result.get("artifact"))
        if (output.format != "image/png" or output.width != payload["width"] or
                output.height != payload["height"]):
            raise AppError(409, "INVALID_RESULT", "Invalid normalized image")
        if not result.get("model_version"):
            raise AppError(409, "INVALID_RESULT", "Missing model version")
        if stage == "NORMALIZE_FACE":
            job.stage = "NORMALIZE_BODY"
            new_output = await create_artifact(session, job, "PREPARED_BODY")
            await make_command(session, cipher, job, "NORMALIZE_BODY", {
                "image_artifact_id": job.body_artifact_id, "output_artifact_id": new_output.id,
                "profile": "full_body", "width": 768, "height": 1024,
            })
        else:
            job.stage = "COLOR_TYPE"
            face = await artifact_of_kind(session, job, "PREPARED_FACE")
            await make_command(session, cipher, job, "COLOR_TYPE", {"image_artifact_id": face.id})
    elif stage == "COLOR_TYPE":
        if result.get("color_type") not in ("spring", "summer", "autumn", "winter"):
            raise AppError(409, "INVALID_RESULT", "Invalid color type")
        if not result.get("model_version"):
            raise AppError(409, "INVALID_RESULT", "Missing model version")
        job.color_type = result["color_type"]
        job.stage = "STYLING"
        await seed_styling(session, cipher, job)
    elif stage == "STYLING":
        outfit, version = result.get("outfit_spec"), result.get("outfit_spec_version")
        if (not isinstance(outfit, dict) or not outfit or not isinstance(version, str) or
                not version or not result.get("model_version") or not result.get("prompt_version")):
            raise AppError(409, "INVALID_RESULT", "Invalid outfit")
        digest = hashlib.sha256(json.dumps({"outfit_spec_version": version, "outfit_spec": outfit},
                                        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        slot = await session.get(ImageSlot, (job.id, command.order_index))
        if await session.get(OutfitReservation, (job.id, digest)):
            await retry_command(session, cipher, job, command, "DUPLICATE_OUTFIT", True,
                                duplicate_hash=digest)
            return
        session.add(OutfitReservation(job_id=job.id, outfit_hash=digest))
        slot.outfit_hash = digest
        slot.outfit_encrypted = cipher.encrypt({"outfit_spec_version": version, "outfit_spec": outfit})
        job.stage = "GENERATION"
        await seed_generation(session, cipher, job, slot)
    elif stage == "GENERATION":
        payload = cipher.decrypt(command.payload_encrypted)
        slot = await session.get(ImageSlot, (job.id, command.order_index))
        output = await session.get(Artifact, payload["output_artifact_id"])
        store_artifact(output, result.get("artifact"))
        if not result.get("model_version") or not result.get("prompt_version"):
            raise AppError(409, "INVALID_RESULT", "Missing generation version")
        output.result_metadata = {"model_version": result["model_version"],
                                  "prompt_version": result["prompt_version"],
                                  "outfit_spec_version": payload["outfit_spec_version"],
                                  "seed": payload["seed"]}
        job.stage = "VERIFICATION"
        await seed_verification(session, cipher, job, slot)
    elif stage == "VERIFICATION":
        slot = await session.get(ImageSlot, (job.id, command.order_index))
        verdict = result.get("verdict")
        if not isinstance(result.get("reason_codes"), list) or not result.get("policy_version"):
            raise AppError(409, "INVALID_RESULT", "Invalid verification metadata")
        if verdict == "INCONCLUSIVE":
            await retry_command(session, cipher, job, command, "VERIFICATION_INCONCLUSIVE", True)
            return
        if verdict == "REJECTED":
            job.failed_attempt_count += 1
            await queue_artifact_cleanup(session, job, slot.candidate_artifact_id, utcnow())
            if slot.candidate_count >= 3:
                await fail_job(session, job, "CANDIDATES_REJECTED")
            else:
                job.stage = "GENERATION"
                await seed_generation(session, cipher, job, slot)
            return
        if verdict != "ACCEPTED":
            raise AppError(409, "INVALID_RESULT", "Invalid verification verdict")
        slot.status, slot.accepted_artifact_id = "ACCEPTED", slot.candidate_artifact_id
        job.accepted_image_count += 1
        job.current_index += 1
        if job.current_index == job.requested_image_count:
            job.status, job.stage = "COMPLETED", "DONE"
            job.result_delivery_status = "AVAILABLE"
            job.results_available_until = utcnow() + timedelta(hours=24)
            await scrub_sensitive(session, job)
        else:
            job.stage = "STYLING"
            await seed_styling(session, cipher, job)
    job.updated_at = utcnow()
    session.add(event_for(job, job.updated_at))
