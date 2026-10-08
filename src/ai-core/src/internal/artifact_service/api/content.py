import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

from botocore.exceptions import ClientError
from fastapi import FastAPI, Header, Request
from fastapi.responses import Response, StreamingResponse

from ..config import Settings
from ..image import ImageError, MEDIA_TYPES, inspect_image
from ..storage import EmptyImage, Storage, StreamTooLarge
from .common import ArtifactError, check_id, not_expired, parse_expiry, parse_range


def register_content(app: FastAPI, settings: Settings, storage: Storage) -> None:
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
