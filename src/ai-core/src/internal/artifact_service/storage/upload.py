import asyncio
import hashlib
import logging
import secrets
from collections.abc import AsyncIterator
from io import BytesIO


class StreamTooLarge(Exception):
    pass


class EmptyImage(Exception):
    pass


logger = logging.getLogger(__name__)


async def upload_stream(
    storage, artifact_id: str, stream: AsyncIterator[bytes], max_bytes: int, content_type: str
) -> tuple[str, bytes, str]:
    key = f"staging/{artifact_id}/{secrets.token_hex(16)}"
    upload_id = None
    completed = False
    collected = BytesIO()
    digest = hashlib.sha256()
    total = 0
    buffer = bytearray()
    parts = []
    part_size = 5 * 1024 * 1024
    try:
        response = await asyncio.to_thread(
            storage.client.create_multipart_upload,
            Bucket=storage.settings.bucket,
            Key=key,
            ContentType=content_type,
        )
        upload_id = response["UploadId"]
        async for chunk in stream:
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise StreamTooLarge
            collected.write(chunk)
            digest.update(chunk)
            buffer.extend(chunk)
            if len(buffer) >= part_size:
                payload = bytes(buffer[:part_size])
                del buffer[:part_size]
                part = await asyncio.to_thread(
                    storage.client.upload_part,
                    Bucket=storage.settings.bucket,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=len(parts) + 1,
                    Body=payload,
                )
                parts.append({"PartNumber": len(parts) + 1, "ETag": part["ETag"]})
        if total == 0:
            raise EmptyImage
        if buffer:
            part = await asyncio.to_thread(
                storage.client.upload_part,
                Bucket=storage.settings.bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=len(parts) + 1,
                Body=bytes(buffer),
            )
            parts.append({"PartNumber": len(parts) + 1, "ETag": part["ETag"]})
        await asyncio.to_thread(
            storage.client.complete_multipart_upload,
            Bucket=storage.settings.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        completed = True
        return key, collected.getvalue(), f"sha256:{digest.hexdigest()}"
    except BaseException:
        if upload_id and not completed:
            try:
                await asyncio.to_thread(
                    storage.client.abort_multipart_upload,
                    Bucket=storage.settings.bucket,
                    Key=key,
                    UploadId=upload_id,
                )
            except Exception:
                logger.exception("failed to abort incomplete artifact upload")
        if completed:
            try:
                await storage.delete_object(key)
            except Exception:
                logger.exception("failed to remove incomplete artifact object")
        raise
