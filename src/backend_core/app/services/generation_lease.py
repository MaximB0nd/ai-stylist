"""Renew database leases while a worker performs network IO."""

import asyncio
from contextlib import asynccontextmanager, suppress

from app.core.config import settings
from app.db.repositories.album_repository import AlbumRepository
from app.db.session import AsyncSessionLocal


class LeaseLostError(RuntimeError):
    """The worker no longer owns the database lease."""


@asynccontextmanager
async def keep_lease(album_id, token):
    owner = asyncio.current_task()
    lost = False

    async def heartbeat():
        nonlocal lost
        try:
            while True:
                await asyncio.sleep(settings.GENERATION_LEASE_SECONDS / 3)
                async with AsyncSessionLocal() as session:
                    if not await AlbumRepository(session).renew_lease(album_id, token):
                        lost = True
                        owner.cancel()
                        return
        except Exception:
            # Stop IO on uncertain ownership. The next recovery pass can reclaim it.
            lost = True
            owner.cancel()

    task = asyncio.create_task(heartbeat())
    try:
        yield
    except asyncio.CancelledError:
        if lost:
            owner.uncancel()
            raise LeaseLostError("Generation lease expired or was replaced") from None
        raise
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
