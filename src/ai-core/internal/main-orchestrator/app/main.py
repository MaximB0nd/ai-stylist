import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import httpx

from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.crypto import Cipher
from app.artifacts import ArtifactClient
from app.dispatch import dispatch_one
from app.errors import AppError
from app.jobs import ack_results, cancel_job, create_job, get_job
from app.imports import process_one_import
from app.results import receive_result
from app.runtime import process_cleanup, process_events, process_expirations
from app.schemas import EmptyBody, JobCreate, WorkerResult
from app.settings import Settings


def create_app(
    settings: Settings | None = None,
    db_probe: Callable[[], Awaitable[bool]] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.artifacts = ArtifactClient(settings.artifact_service_url) if settings.artifact_service_url else None
        application.state.http = httpx.AsyncClient(timeout=30)
        async def run() -> None:
            while True:
                try:
                    await process_expirations(application.state.sessions)
                    await process_one_import(application.state.sessions, application.state.cipher, application.state.artifacts)
                    await process_events(application.state.sessions, application.state.cipher)
                    await dispatch_one(application.state.sessions, application.state.cipher,
                                       settings.worker_urls, application.state.artifacts, application.state.http)
                    await process_cleanup(application.state.sessions, application.state.artifacts)
                except Exception:
                    application.state.logger.exception("Orchestrator background cycle failed")
                await asyncio.sleep(1)
        import logging
        application.state.logger = logging.getLogger("orchestrator")
        task = asyncio.create_task(run())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            if application.state.artifacts:
                await application.state.artifacts.close()
            await application.state.http.aclose()
            await application.state.engine.dispose()

    app = FastAPI(title="AI Core Main Orchestrator", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.sessions = async_sessionmaker(app.state.engine, expire_on_commit=False)
    app.state.cipher = Cipher(settings.encryption_key.get_secret_value())

    @app.exception_handler(AppError)
    async def app_error(_, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_, __: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"code": "INVALID_REQUEST", "message": "Invalid request", "retryable": False},
        )

    @app.get("/internal/ready")
    async def ready() -> JSONResponse:
        try:
            if db_probe is not None:
                database_ready = await db_probe()
            else:
                async with app.state.engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                database_ready = True
        except Exception:
            database_ready = False
        artifact_status = "not_configured"
        if settings.artifact_service_url:
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    response = await client.get(f"{settings.artifact_service_url.rstrip('/')}/internal/ready")
                artifact_status = "ready" if response.status_code == 200 and response.json().get("ready") else "unavailable"
            except (httpx.HTTPError, ValueError):
                artifact_status = "unavailable"
        return JSONResponse(
            status_code=200 if database_ready else 503,
            content={
                "ready": database_ready,
                "database": "ready" if database_ready else "unavailable",
                "artifact_service": artifact_status,
            },
        )

    @app.post("/internal/v1/jobs")
    async def create(body: JobCreate) -> JSONResponse:
        job_id, created = await create_job(app.state.sessions, app.state.cipher, body)
        view = await get_job(app.state.sessions, job_id)
        return JSONResponse(status_code=201 if created else 200, content=view)

    @app.get("/internal/v1/jobs/{job_id}")
    async def get(job_id: str) -> dict:
        artifacts = getattr(app.state, "artifacts", None)
        return await get_job(app.state.sessions, job_id, artifacts)

    @app.post("/internal/v1/jobs/{job_id}/cancel")
    async def cancel(job_id: str, _: EmptyBody = Body(...)) -> dict:
        return await cancel_job(app.state.sessions, job_id)

    @app.post("/internal/v1/jobs/{job_id}/results/ack", status_code=204)
    async def ack(job_id: str, _: EmptyBody = Body(...)) -> None:
        await ack_results(app.state.sessions, job_id)

    @app.post("/internal/v1/worker-results", status_code=204)
    async def worker_result(body: WorkerResult) -> None:
        await receive_result(app.state.sessions, app.state.cipher, body)

    return app
