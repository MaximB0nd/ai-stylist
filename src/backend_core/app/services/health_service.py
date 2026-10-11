"""Bounded readiness probes for PostgreSQL and the media bucket."""

import asyncio

from sqlalchemy import text
from urllib3 import PoolManager, Retry, Timeout

from app.core.config import settings
from app.db.session import engine
from minio import Minio


async def check_postgres():
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


def check_minio():
    # A separate bounded transport prevents timed-out probes occupying threads indefinitely.
    transport = PoolManager(timeout=Timeout(connect=2, read=2), retries=Retry(total=0))
    try:
        client = Minio(
            settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY, secure=settings.MINIO_SECURE,
            http_client=transport,
        )
        if not client.bucket_exists(settings.MINIO_BUCKET):
            raise RuntimeError("Media bucket does not exist")
    finally:
        transport.clear()


async def readiness():
    async def probe(name, operation):
        try:
            await asyncio.wait_for(operation(), timeout=5)
            return name, "ok"
        except Exception:
            return name, "unavailable"

    checks = dict(await asyncio.gather(
        probe("postgresql", check_postgres),
        probe("minio", lambda: asyncio.to_thread(check_minio)),
    ))
    return checks
