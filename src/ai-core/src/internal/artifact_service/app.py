import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .api.content import register_content
from .api.errors import register_error_handlers
from .api.importing import register_import
from .api.lifecycle import register_lifecycle
from .config import Settings
from .storage import Storage


logger = logging.getLogger(__name__)


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
    register_error_handlers(app)
    register_lifecycle(app, settings, storage)
    register_import(app, settings, storage, source_transport)
    register_content(app, settings, storage)
    return app
