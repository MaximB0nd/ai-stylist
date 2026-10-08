import asyncio
import hashlib
import json
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .image import ImageError, MEDIA_TYPES, inspect_image
from .storage import EmptyImage, Storage, StreamTooLarge


ULID = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
logger = logging.getLogger(__name__)


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str
    max_size_bytes: int = Field(gt=0)
    expires_at: datetime


class ArtifactError(Exception):
    def __init__(self, status: int, code: str, *, retryable: bool = False, retry_after: int | None = None):
        self.status = status
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_expiry(value: datetime, settings: Settings) -> str:
    now = utcnow()
    if value.tzinfo is None or not (now < value <= now + timedelta(seconds=settings.max_lifetime_seconds)):
        raise ArtifactError(422, "VALIDATION_ERROR")
    return value.astimezone(timezone.utc).isoformat()


def not_expired(state: dict) -> bool:
    return datetime.fromisoformat(state["expires_at"]) > utcnow()


def validate_source_url(source_url: str, origin: str) -> None:
    try:
        parsed = urlsplit(source_url)
        allowed = urlsplit(origin)
        valid = (
            parsed.scheme == "http"
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and bool(parsed.hostname)
            and (parsed.scheme, parsed.hostname.lower(), parsed.port or 80)
            == (allowed.scheme, allowed.hostname.lower(), allowed.port or 80)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ArtifactError(422, "SOURCE_URL_NOT_ALLOWED")


def parse_range(value: str | None, size: int) -> tuple[str | None, int, int]:
    if value is None:
        return None, 0, size - 1
    match = RANGE.fullmatch(value)
    if not match or not any(match.groups()) or size < 1:
        raise ArtifactError(416, "INVALID_RANGE")
    first, last = match.groups()
    if first:
        start = int(first)
        end = int(last) if last else size - 1
    else:
        count = int(last)
        if count == 0:
            raise ArtifactError(416, "INVALID_RANGE")
        start = max(0, size - count)
        end = size - 1
    if start >= size or end < start:
        raise ArtifactError(416, "INVALID_RANGE")
    end = min(end, size - 1)
    return f"bytes={start}-{end}", start, end


def create_app(settings: Settings | None = None, storage: Storage | None = None, source_transport=None) -> FastAPI:
    settings = settings or Settings()
    storage = storage or Storage(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await storage.ensure_bucket()
        await storage.cleanup_expired()

        async def cleanup_loop():
            while True:
                await asyncio.sleep(settings.cleanup_interval_seconds)
                try:
                    await storage.cleanup_expired()
                except Exception:
                    logger.exception("artifact cleanup failed")

        task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="AI Stylist artifact service", lifespan=lifespan)

    @app.exception_handler(ArtifactError)
    async def artifact_error(_request: Request, error: ArtifactError):
        headers = {"Content-Type": "application/problem+json"}
        if error.retry_after is not None:
            headers["Retry-After"] = str(error.retry_after)
        return JSONResponse(
            {
                "type": "about:blank",
                "title": error.code.replace("_", " ").title(),
                "status": error.status,
                "code": error.code,
                "retryable": error.retryable,
            },
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(BotoCoreError)
    @app.exception_handler(ClientError)
    async def storage_error(request: Request, _error: Exception):
        return await artifact_error(request, ArtifactError(502, "STORAGE_UNAVAILABLE", retryable=True))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        malformed = any(item["type"] == "json_invalid" for item in error.errors())
        return await artifact_error(
            request, ArtifactError(400 if malformed else 422, "MALFORMED_REQUEST" if malformed else "VALIDATION_ERROR")
        )

    def check_id(artifact_id: str) -> None:
        if not ULID.fullmatch(artifact_id):
            raise ArtifactError(422, "VALIDATION_ERROR")

    def content_url(artifact_id: str) -> str:
        return f"{settings.public_base_url}/internal/v1/artifacts/{artifact_id}/content"

    async def metadata_response(artifact_id: str, state: dict) -> dict:
        return {
            "artifact_id": artifact_id,
            "checksum_sha256": state["checksum_sha256"],
            "media_type": state["media_type"],
            "size_bytes": state["size_bytes"],
            "width": state["width"],
            "height": state["height"],
            "url": content_url(artifact_id),
        }

    @app.get("/internal/ready")
    async def ready():
        if not await storage.ready():
            raise ArtifactError(503, "STORAGE_UNAVAILABLE", retryable=True)
        return {"status": "ready"}

    @app.post("/internal/v1/artifacts/{artifact_id}/content")
    async def import_artifact(artifact_id: str, payload: ImportRequest):
        check_id(artifact_id)
        validate_source_url(payload.source_url, settings.source_origin)
        if payload.max_size_bytes > settings.max_size_bytes:
            raise ArtifactError(422, "VALIDATION_ERROR")
        expiry = parse_expiry(payload.expires_at, settings)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "source_url": payload.source_url,
                    "max_size_bytes": payload.max_size_bytes,
                    "expires_at": expiry,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        async with storage.lock:
            state = await storage.get_state(artifact_id)
            if state is not None:
                if state.get("source_hash") != fingerprint or state["status"] == "DELETED" or not not_expired(state):
                    raise ArtifactError(409, "ARTIFACT_CONFLICT")
                if state["status"] == "PUBLISHED":
                    return JSONResponse(await metadata_response(artifact_id, state), status_code=200)
                if artifact_id in storage.active:
                    raise ArtifactError(409, "IMPORT_IN_PROGRESS", retryable=True, retry_after=1)
            else:
                await storage.put_state(
                    artifact_id, {"status": "IMPORTING", "expires_at": expiry, "source_hash": fingerprint}
                )
            storage.active.add(artifact_id)

        blob_key = None
        try:
            timeout = httpx.Timeout(connect=5, read=30, write=10, pool=5)
            async with asyncio.timeout(60):
                async with httpx.AsyncClient(
                    timeout=timeout, follow_redirects=False, trust_env=False, transport=source_transport
                ) as client:
                    async with client.stream("GET", payload.source_url) as source:
                        if source.status_code in (401, 403, 404):
                            raise ArtifactError(422, "SOURCE_NOT_ACCESSIBLE")
                        if source.status_code == 429 or source.status_code >= 500:
                            raise ArtifactError(502, "SOURCE_UNAVAILABLE", retryable=True)
                        if source.status_code != 200:
                            raise ArtifactError(422, "SOURCE_URL_NOT_ALLOWED")
                        blob_key, data, checksum = await storage.upload_stream(
                            artifact_id, source.aiter_bytes(), payload.max_size_bytes, "application/octet-stream"
                        )
            info = inspect_image(
                data,
                max_dimension=settings.max_dimension,
                max_pixels=settings.max_dimension**2,
                max_exif_bytes=settings.max_exif_bytes,
                max_icc_bytes=settings.max_icc_bytes,
            )
            async with storage.lock:
                current = await storage.get_state(artifact_id)
                if current["status"] == "DELETED" or not not_expired(current):
                    raise ArtifactError(409, "ARTIFACT_CONFLICT")
                current.update(
                    status="PUBLISHED",
                    blob_key=blob_key,
                    checksum_sha256=checksum,
                    media_type=info.media_type,
                    size_bytes=len(data),
                    width=info.width,
                    height=info.height,
                )
                await storage.put_state(artifact_id, current)
            blob_key = None
            return JSONResponse(await metadata_response(artifact_id, current), status_code=201)
        except StreamTooLarge as exc:
            raise ArtifactError(422, "SOURCE_TOO_LARGE") from exc
        except EmptyImage as exc:
            raise ArtifactError(422, "SOURCE_UNPROCESSABLE") from exc
        except ImageError as exc:
            code = {
                "UNSUPPORTED_IMAGE_TYPE": "SOURCE_UNSUPPORTED_IMAGE_TYPE",
                "UNPROCESSABLE_IMAGE": "SOURCE_UNPROCESSABLE",
            }.get(exc.code, exc.code)
            raise ArtifactError(422, code) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ArtifactError(504, "SOURCE_TIMEOUT", retryable=True) from exc
        except httpx.RequestError as exc:
            raise ArtifactError(502, "SOURCE_UNAVAILABLE", retryable=True) from exc
        finally:
            if blob_key is not None:
                await storage.delete_object(blob_key)
            async with storage.lock:
                storage.active.discard(artifact_id)

    @app.put("/internal/v1/artifacts/{artifact_id}/content")
    async def put_content(
        artifact_id: str,
        request: Request,
        content_type: str | None = Header(default=None),
        x_artifact_expires_at: str | None = Header(default=None),
    ):
        check_id(artifact_id)
        if content_type not in MEDIA_TYPES.values():
            raise ArtifactError(415, "UNSUPPORTED_IMAGE_TYPE")
        if x_artifact_expires_at is None:
            raise ArtifactError(422, "VALIDATION_ERROR")
        try:
            expiry = parse_expiry(datetime.fromisoformat(x_artifact_expires_at.replace("Z", "+00:00")), settings)
        except ValueError as exc:
            raise ArtifactError(422, "VALIDATION_ERROR") from exc
        async with storage.lock:
            state = await storage.get_state(artifact_id)
            if state is None:
                await storage.put_state(
                    artifact_id, {"status": "WRITABLE", "expires_at": expiry, "media_type": content_type}
                )
            elif state["status"] != "WRITABLE" or state["expires_at"] != expiry or state["media_type"] != content_type or not not_expired(state):
                raise ArtifactError(409, "ARTIFACT_NOT_WRITABLE")
            if artifact_id in storage.active:
                raise ArtifactError(409, "TRANSFER_IN_PROGRESS", retryable=True, retry_after=1)
            storage.active.add(artifact_id)
        blob_key = None
        try:
            blob_key, data, checksum = await storage.upload_stream(
                artifact_id, request.stream(), settings.max_size_bytes, content_type
            )
            info = inspect_image(
                data,
                content_type,
                max_dimension=settings.max_dimension,
                max_pixels=settings.max_dimension**2,
                max_exif_bytes=settings.max_exif_bytes,
                max_icc_bytes=settings.max_icc_bytes,
            )
            async with storage.lock:
                current = await storage.get_state(artifact_id)
                if current["status"] != "WRITABLE" or not not_expired(current):
                    raise ArtifactError(409, "ARTIFACT_NOT_WRITABLE")
                current.update(
                    status="PUBLISHED",
                    blob_key=blob_key,
                    checksum_sha256=checksum,
                    size_bytes=len(data),
                    width=info.width,
                    height=info.height,
                )
                await storage.put_state(artifact_id, current)
            blob_key = None
            return Response(status_code=204)
        except StreamTooLarge as exc:
            raise ArtifactError(413, "IMAGE_TOO_LARGE") from exc
        except EmptyImage as exc:
            raise ArtifactError(422, "UNPROCESSABLE_IMAGE") from exc
        except ImageError as exc:
            raise ArtifactError(422, exc.code) from exc
        finally:
            if blob_key is not None:
                await storage.delete_object(blob_key)
            async with storage.lock:
                storage.active.discard(artifact_id)

    @app.get("/internal/v1/artifacts/{artifact_id}/content")
    async def get_content(artifact_id: str, range_header: str | None = Header(default=None, alias="Range")):
        check_id(artifact_id)
        state = await storage.get_state(artifact_id)
        if state is None or state["status"] != "PUBLISHED" or not not_expired(state):
            raise ArtifactError(404, "ARTIFACT_NOT_FOUND")
        size = state["size_bytes"]
        byte_range, start, end = parse_range(range_header, size)
        try:
            obj = await storage.open_object(state["blob_key"], byte_range)
        except ClientError as exc:
            raise ArtifactError(502, "STORAGE_UNAVAILABLE", retryable=True) from exc
        body = obj["Body"]

        async def chunks() -> AsyncIterator[bytes]:
            remaining = end - start + 1
            try:
                while remaining:
                    chunk = await asyncio.to_thread(body.read, min(64 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            finally:
                body.close()

        headers = {
            "Content-Length": str(end - start + 1),
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-store",
        }
        if byte_range is not None:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return StreamingResponse(
            chunks(), status_code=206 if byte_range else 200, media_type=state["media_type"], headers=headers
        )

    @app.delete("/internal/v1/artifacts/{artifact_id}")
    async def delete_artifact(artifact_id: str):
        check_id(artifact_id)
        async with storage.lock:
            state = await storage.get_state(artifact_id)
            if state is None:
                state = {
                    "status": "DELETED",
                    "expires_at": (utcnow() + timedelta(seconds=settings.max_lifetime_seconds)).isoformat(),
                }
            else:
                state["status"] = "DELETED"
            await storage.put_state(artifact_id, state)
        if state.get("blob_key"):
            await storage.delete_object(state["blob_key"])
        return Response(status_code=204)

    return app
