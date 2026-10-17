import asyncio
import json
from collections.abc import AsyncIterator

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from ..config import Settings
from .cleanup import cleanup_expired
from .upload import upload_stream


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
        return await upload_stream(self, artifact_id, stream, max_bytes, content_type)

    async def open_object(self, key: str, byte_range: str | None = None):
        args = {"Bucket": self.settings.bucket, "Key": key}
        if byte_range is not None:
            args["Range"] = byte_range
        return await asyncio.to_thread(self.client.get_object, **args)

    async def cleanup_expired(self) -> None:
        await cleanup_expired(self)
