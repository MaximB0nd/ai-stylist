import asyncio
import logging
from typing import BinaryIO

from fastapi import UploadFile
from minio import Minio

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Thin wrapper around MinIO client for S3-compatible storage operations."""

    def __init__(self) -> None:
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        # Dedicated client for browser-facing presigned URLs (resolves localhost/public domains)
        public_endpoint = settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT
        clean_public_endpoint = (
            public_endpoint.replace("http://", "").replace("https://", "").rstrip("/")
        )
        public_secure = (
            settings.MINIO_PUBLIC_SECURE
            if settings.MINIO_PUBLIC_SECURE is not None
            else settings.MINIO_SECURE
        )
        self.public_client = Minio(
            endpoint=clean_public_endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=public_secure,
        )
        self.bucket = settings.MINIO_BUCKET
        self.presigned_ttl = settings.MINIO_PRESIGNED_TTL


    def _ensure_bucket(self) -> None:
        """Create bucket if it does not exist (idempotent)."""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def upload_file(self, object_key: str, file: UploadFile) -> str:
        """Upload a file to MinIO. Returns the object key."""
        content = await file.read()
        length = len(content)

        import io

        data_stream = io.BytesIO(content)

        # MinIO client is synchronous, offload to thread pool
        await asyncio.to_thread(
            self._put_object, object_key, data_stream, length, file.content_type or "application/octet-stream"
        )
        return object_key

    async def upload_bytes(self, object_key: str, data: bytes, content_type: str = "image/webp") -> str:
        """Upload raw bytes to MinIO. Returns the object key."""
        import io

        data_stream = io.BytesIO(data)
        await asyncio.to_thread(
            self._put_object, object_key, data_stream, len(data), content_type
        )
        return object_key

    def _put_object(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        """Synchronous put_object call for use with asyncio.to_thread."""
        self._ensure_bucket()
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=key,
            data=data,
            length=length,
            content_type=content_type,
        )

    def presigned_public_url(self, object_key: str) -> str:
        """Generate a presigned GET URL using public endpoint for browser/client consumption."""
        from datetime import timedelta

        client = getattr(self, "public_client", getattr(self, "client", None))
        if client is None or not hasattr(client, "presigned_get_object"):
            return getattr(self, "presigned_url", lambda k: f"http://localhost:9000/{getattr(self, 'bucket', 'stylist')}/{k}")(object_key)

        return client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_key,
            expires=timedelta(seconds=self.presigned_ttl),
        )

    def presigned_internal_url(self, object_key: str) -> str:
        """Generate a presigned GET URL using internal endpoint for backend/AI Core consumption."""
        from datetime import timedelta

        client = getattr(self, "client", None)
        if client is None or not hasattr(client, "presigned_get_object"):
            return getattr(self, "presigned_url", lambda k: f"http://minio:9000/{getattr(self, 'bucket', 'stylist')}/{k}")(object_key)

        return client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_key,
            expires=timedelta(seconds=self.presigned_ttl),
        )

    def presigned_url(self, object_key: str) -> str:
        """Generate a presigned GET URL (defaults to public URL for client compatibility)."""
        client = getattr(self, "public_client", getattr(self, "client", None))
        if client is None or not hasattr(client, "presigned_get_object"):
            return f"http://localhost:9000/{getattr(self, 'bucket', 'stylist')}/{object_key}"
        return self.presigned_public_url(object_key)



