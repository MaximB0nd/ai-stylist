import asyncio
import hashlib
import json
import logging
import secrets
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from io import BytesIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import Settings


class StreamTooLarge(Exception):
    pass


class EmptyImage(Exception):
    pass


logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self.lock = asyncio.Lock()
        self.active: set[str] = set()

    async def ready(self) -> bool:
        try:
            await asyncio.to_thread(self.client.head_bucket, Bucket=self.settings.bucket)
            return True
        except Exception:
            return False

    async def ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(self.client.head_bucket, Bucket=self.settings.bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
            await asyncio.to_thread(self.client.create_bucket, Bucket=self.settings.bucket)

    @staticmethod
    def state_key(artifact_id: str) -> str:
        return f"state/{artifact_id}.json"

    async def get_state(self, artifact_id: str) -> dict | None:
        try:
            response = await asyncio.to_thread(
                self.client.get_object, Bucket=self.settings.bucket, Key=self.state_key(artifact_id)
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return None
            raise
        body = response["Body"]
        try:
            return json.loads(await asyncio.to_thread(body.read))
        finally:
            body.close()

    async def put_state(self, artifact_id: str, state: dict) -> None:
        payload = json.dumps(state, separators=(",", ":"), sort_keys=True).encode()
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.settings.bucket,
            Key=self.state_key(artifact_id),
            Body=payload,
            ContentType="application/json",
        )

    async def delete_object(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.settings.bucket, Key=key)

    async def upload_stream(
        self, artifact_id: str, stream: AsyncIterator[bytes], max_bytes: int, content_type: str
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
                self.client.create_multipart_upload,
                Bucket=self.settings.bucket,
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
                        self.client.upload_part,
                        Bucket=self.settings.bucket,
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
                    self.client.upload_part,
                    Bucket=self.settings.bucket,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=len(parts) + 1,
                    Body=bytes(buffer),
                )
                parts.append({"PartNumber": len(parts) + 1, "ETag": part["ETag"]})
            await asyncio.to_thread(
                self.client.complete_multipart_upload,
                Bucket=self.settings.bucket,
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
                        self.client.abort_multipart_upload,
                        Bucket=self.settings.bucket,
                        Key=key,
                        UploadId=upload_id,
                    )
                except Exception:
                    logger.exception("failed to abort incomplete artifact upload")
            if completed:
                try:
                    await self.delete_object(key)
                except Exception:
                    logger.exception("failed to remove incomplete artifact object")
            raise

    async def open_object(self, key: str, byte_range: str | None = None):
        args = {"Bucket": self.settings.bucket, "Key": key}
        if byte_range is not None:
            args["Range"] = byte_range
        return await asyncio.to_thread(self.client.get_object, **args)

    async def _list_objects(self, prefix: str) -> list[dict]:
        items = []
        continuation = None
        while True:
            args = {"Bucket": self.settings.bucket, "Prefix": prefix}
            if continuation:
                args["ContinuationToken"] = continuation
            page = await asyncio.to_thread(self.client.list_objects_v2, **args)
            items.extend(page.get("Contents", []))
            continuation = page.get("NextContinuationToken")
            if not continuation:
                return items

    async def cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        referenced = set()
        async with self.lock:
            for item in await self._list_objects("state/"):
                artifact_id = item["Key"].removeprefix("state/").removesuffix(".json")
                state = await self.get_state(artifact_id)
                if state is None:
                    continue
                blob_key = state.get("blob_key")
                if artifact_id in self.active or datetime.fromisoformat(state["expires_at"]) > now:
                    if blob_key:
                        referenced.add(blob_key)
                    continue
                if blob_key:
                    await self.delete_object(blob_key)
                await self.delete_object(self.state_key(artifact_id))
            orphan_cutoff = now - timedelta(hours=1)
            for item in await self._list_objects("staging/"):
                if item["Key"] not in referenced and item["LastModified"] < orphan_cutoff:
                    await self.delete_object(item["Key"])
            uploads = await asyncio.to_thread(self.client.list_multipart_uploads, Bucket=self.settings.bucket)
            for upload in uploads.get("Uploads", []):
                if upload["Initiated"] < orphan_cutoff:
                    await asyncio.to_thread(
                        self.client.abort_multipart_upload,
                        Bucket=self.settings.bucket,
                        Key=upload["Key"],
                        UploadId=upload["UploadId"],
                    )
