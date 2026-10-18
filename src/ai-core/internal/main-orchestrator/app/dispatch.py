from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts import ArtifactClient, ArtifactFailure
from app.crypto import Cipher
from app.db import Artifact, Command, Job, utcnow
from app.errors import AppError
from app.pipeline import apply_success, fail_job, retry_command

ENDPOINTS = {
    "FACE_VALIDATION": "/v1/validate", "BODY_VALIDATION": "/v1/validate",
    "IDENTITY_VERIFICATION": "/v1/compare",
    "NORMALIZE_FACE": "/v1/normalize", "NORMALIZE_BODY": "/v1/normalize",
    "COLOR_TYPE": "/v1/classify", "STYLING": "/v1/style",
    "GENERATION": "/v1/generate", "VERIFICATION": "/v1/verify",
}


async def hydrate(session: AsyncSession, payload: dict, stage: str,
                  artifacts: ArtifactClient | None) -> dict:
    if stage == "STYLING":
        return payload
    if artifacts is None:
        raise ArtifactFailure("ARTIFACT_SERVICE_UNAVAILABLE", True)

    async def image(key: str) -> dict:
        value = await session.get(Artifact, payload[key])
        link = await artifacts.access(value.id, "READ")
        return {"read_url": link["url"], "checksum_sha256": value.checksum_sha256}

    if stage in ("FACE_VALIDATION", "BODY_VALIDATION", "COLOR_TYPE"):
        return {"image": await image("image_artifact_id")}
    if stage == "IDENTITY_VERIFICATION":
        return {"face_image": await image("face_artifact_id"),
                "body_image": await image("body_artifact_id")}
    if stage in ("NORMALIZE_FACE", "NORMALIZE_BODY"):
        link = await artifacts.access(payload["output_artifact_id"], "WRITE", "image/png")
        return {"profile": payload["profile"], "image": await image("image_artifact_id"),
                "output": {"write_url": link["url"], "width": payload["width"],
                           "height": payload["height"]}}
    if stage == "GENERATION":
        link = await artifacts.access(payload["output_artifact_id"], "WRITE")
        return {"face_image": await image("face_artifact_id"),
                "body_image": await image("body_artifact_id"),
                "outfit_spec_version": payload["outfit_spec_version"],
                "outfit_spec": payload["outfit_spec"], "seed": payload["seed"],
                "output": {"write_url": link["url"]}}
    if stage == "VERIFICATION":
        return {"face_image": await image("face_artifact_id"),
                "body_image": await image("body_artifact_id"),
                "candidate_image": await image("candidate_artifact_id"),
                "outfit_spec_version": payload["outfit_spec_version"],
                "outfit_spec": payload["outfit_spec"]}
    raise ValueError(stage)


def retry_after(response: httpx.Response) -> int:
    try:
        return max(1, min(300, int(response.headers.get("Retry-After", "5"))))
    except ValueError:
        return 5


def public_failure(stage: str, code: str) -> str:
    if code == "COLOR_TYPE_UNCERTAIN":
        return code
    if code in {"INVALID_NORMALIZED_IMAGE", "INPUT_UNAVAILABLE", "OUTPUT_UNAVAILABLE",
                "MODEL_UNAVAILABLE", "INPUT_TIMEOUT", "OUTPUT_TIMEOUT", "WORKER_UNREACHABLE"}:
        return "PREPROCESSING_UNAVAILABLE" if stage in {
            "FACE_VALIDATION", "BODY_VALIDATION", "IDENTITY_VERIFICATION",
            "NORMALIZE_FACE", "NORMALIZE_BODY", "COLOR_TYPE"} else code
    if code in {"PERSON_MASK_UNAVAILABLE", "SOURCE_UNPROCESSABLE", "INPUT_UNPROCESSABLE",
                "SOURCE_UNSUPPORTED_IMAGE_TYPE", "UNSUPPORTED_IMAGE_TYPE"}:
        return "PHOTO_UNPROCESSABLE"
    if stage == "IDENTITY_VERIFICATION" and code.startswith(("FACE_IMAGE_", "BODY_IMAGE_")):
        return "PHOTO_UNPROCESSABLE"
    return code


async def dispatch_one(sessions: async_sessionmaker[AsyncSession], cipher: Cipher,
                       worker_urls: dict[str, str], artifacts: ArtifactClient | None,
                       client: httpx.AsyncClient, job_id: str | None = None) -> bool:
    now = utcnow()
    async with sessions.begin() as session:
        query = select(Command).where(Command.status.in_(("PENDING", "SENDING")),
                                      Command.next_send_at <= now)
        if job_id is not None:
            query = query.where(Command.job_id == job_id)
        command = (await session.execute(query.order_by(Command.next_send_at, Command.created_at)
                                         .limit(1).with_for_update(skip_locked=True))).scalar_one_or_none()
        if command is None:
            return False
        job = await session.get(Job, command.job_id)
        if job.status not in ("QUEUED", "PROCESSING"):
            command.status = "CANCELLED"
            return True
        command.status = "SENDING"
        command.sent_count += 1
        command.next_send_at = now + timedelta(minutes=31)
        selected = (command.id, command.job_id, command.stage,
                    command.payload_encrypted)

    command_id, selected_job_id, stage, encrypted = selected
    base = worker_urls.get(stage)
    if not base:
        outcome = ("WAIT", None, 60)
    else:
        try:
            async with sessions() as session:
                body = await hydrate(session, cipher.decrypt(encrypted), stage, artifacts)
            response = await client.post(f"{base.rstrip('/')}{ENDPOINTS[stage]}",
                                         json={"request_id": command_id, **body})
            if response.status_code == 200:
                outcome = ("SUCCESS", response.json(), 0)
            elif response.status_code == 429:
                outcome = ("WAIT", None, retry_after(response))
            else:
                try:
                    problem = response.json()
                except ValueError:
                    problem = {}
                outcome = ("FAIL", (str(problem.get("code", "WORKER_UNAVAILABLE")),
                                    bool(problem.get("retryable", response.status_code >= 500))), 0)
        except ArtifactFailure as exc:
            outcome = ("WAIT", None, 60) if exc.retryable else ("FAIL", (exc.code, False), 0)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            outcome = ("FAIL", ("WORKER_UNREACHABLE", True), 0)

    async with sessions.begin() as session:
        job = (await session.execute(select(Job).where(Job.id == selected_job_id).with_for_update())).scalar_one()
        command = (await session.execute(select(Command).where(Command.id == command_id).with_for_update())).scalar_one()
        if command.status != "SENDING":
            return True
        if job.status not in ("QUEUED", "PROCESSING"):
            command.status = "CANCELLED"
            return True
        kind, value, delay = outcome
        if kind == "WAIT":
            command.status = "PENDING"
            command.next_send_at = utcnow() + timedelta(seconds=delay)
        elif kind == "FAIL":
            code, retryable = value
            await retry_command(session, cipher, job, command, code, retryable,
                                public_code=public_failure(stage, code))
            command.error_code, command.error_retryable = code, retryable
            command.status = "DONE"
        else:
            try:
                await apply_success(session, cipher, job, command, value)
            except (AppError, KeyError, TypeError, ValueError):
                await fail_job(session, job, "INVALID_WORKER_RESULT")
            command.status = "DONE"
            if job.status not in ("COMPLETED", "FAILED", "CANCELLED"):
                command.result_encrypted = cipher.encrypt(value)
    return True
