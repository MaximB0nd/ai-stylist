import asyncio
import hashlib
import json

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ..config import Settings
from ..image import ImageError, inspect_image
from ..storage import EmptyImage, Storage, StreamTooLarge
from .common import ArtifactError, ImportRequest, check_id, not_expired, parse_expiry, validate_source_url


def register_import(app: FastAPI, settings: Settings, storage: Storage, source_transport=None) -> None:
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
