import asyncio
import logging
from typing import BinaryIO

from fastapi import UploadFile
from minio import Minio
from urllib3 import PoolManager, Retry, Timeout

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
            http_client=PoolManager(
                timeout=Timeout(connect=3, read=15),
                retries=Retry(total=2, backoff_factor=0.2,
                              status_forcelist=[500, 502, 503, 504]),
            ),
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
            region="us-east-1",
        )
        self.bucket = settings.MINIO_BUCKET
        self.presigned_ttl = settings.MINIO_PRESIGNED_TTL


    def _ensure_bucket(self) -> None:
        """Create bucket if it does not exist (idempotent) and configure lifecycle rules."""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        self._ensure_lifecycle_rules()

    def _ensure_lifecycle_rules(self) -> None:
        """Configure S3 lifecycle rules to automatically purge source photos after 1 day.

        Protects MinIO storage from disk exhaustion by purging temporary face/body source photos
        once generation is completed.
        """
        try:
            from minio.commonconfig import ENABLED, Filter
            from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

            rule = Rule(
                status=ENABLED,
                rule_filter=Filter(prefix="sources/"),
                rule_id="expire-sources-1-day",
                expiration=Expiration(days=1),
            )
            config = LifecycleConfig([rule])
            self.client.set_bucket_lifecycle(self.bucket, config)
            logger.info("Configured MinIO lifecycle rule: purge 'sources/' after 1 day.")
        except Exception as exc:
            logger.warning("Could not set bucket lifecycle rules on '%s': %s", self.bucket, exc)

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

    async def upload_bytes(self, object_key: str, data: bytes, content_type: str = "image/png") -> str:
        """Upload raw bytes to MinIO. Returns the object key."""
        import io

        data_stream = io.BytesIO(data)
        upload = asyncio.create_task(asyncio.to_thread(
            self._put_object, object_key, data_stream, len(data), content_type
        ))
        try:
            await asyncio.shield(upload)
        except asyncio.CancelledError:
            # A cancelled await cannot stop a synchronous S3 PUT. Drain it before cleanup.
            await asyncio.gather(upload, return_exceptions=True)
            raise
        return object_key

    async def delete_object(self, object_key: str) -> None:
        """Remove only the explicitly named object of an unsuccessful source attempt."""
        await asyncio.to_thread(self.client.remove_object, self.bucket, object_key)

    async def download_bytes(self, object_key: str, max_bytes: int) -> bytes:
        """Read a legacy result with a strict compressed-byte budget."""
        def read():
            response = self.client.get_object(self.bucket, object_key)
            try:
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    from app.services.image_service import ImageTooLarge
                    raise ImageTooLarge("Stored image exceeds 15 MiB")
                return data
            finally:
                response.close()
                response.release_conn()
        return await asyncio.to_thread(read)

    def _put_object(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        """Synchronous put_object call for use with asyncio.to_thread.

        Does not call _ensure_bucket() on every upload, avoiding redundant HTTP round-trips.
        Bucket creation is guaranteed once at application startup.
        """
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

        region = self.client._get_region(self.bucket)
        client = Minio(
            endpoint=client._base_url.host,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=client._base_url.is_https,
            region=region,
        )
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




    def list_attempt_objects(self):
        return list(self.client.list_objects(self.bucket, prefix="albums/", recursive=True))

    def delete_attempt(self, prefix):
        for obj in self.client.list_objects(self.bucket, prefix=prefix, recursive=True):
            self.client.remove_object(self.bucket, obj.object_name)
