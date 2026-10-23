import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: verify or create MinIO bucket on startup."""
    try:
        from app.services.storage_service import StorageService

        storage = StorageService()
        await asyncio.to_thread(storage._ensure_bucket)
        logger.info("MinIO bucket '%s' ready.", storage.bucket)
    except Exception as e:
        logger.warning("Could not auto-create MinIO bucket on startup: %s", e)

    from app.services.generation_recovery import recovery_loop
    from app.services.generation_queue import get_generation_queue
    delivery_queue = get_generation_queue()
    delivery_queue.start()
    recovery_task = asyncio.create_task(recovery_loop())
    monitoring_task = None
    if settings.ADMIN_ENABLED:
        from app.services.admin_monitoring_service import monitoring_loop
        monitoring_task = asyncio.create_task(monitoring_loop())
    try:
        yield
    finally:
        if monitoring_task is not None:
            monitoring_task.cancel()
            with suppress(asyncio.CancelledError):
                await monitoring_task
        recovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await recovery_task
        await delivery_queue.close()

    # Graceful shutdown: close PostgreSQL connection pool
    try:
        from app.db.session import engine
        await engine.dispose()
        logger.info("Closed PostgreSQL connection pool.")
    except Exception as e:
        logger.warning("Error disposing database engine on shutdown: %s", e)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    # Swagger UI and OpenAPI schema are disabled in production to avoid leaking internal API details
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# CORS configuration:
# - Explicit origins from config (exact match, safe with allow_credentials=True)
# - No allow_origin_regex: regex like r"localhost:\d+" would allow any local port
#   with credentials, creating a security hole for malicious browser extensions.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map request validation errors to 400 Bad Request for auth endpoints per contract."""
    if request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth"):
        errors = exc.errors()
        error_msgs = [f"{err.get('loc', ['field'])[-1]}: {err.get('msg', 'invalid')}" for err in errors]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "; ".join(error_msgs)},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": exc.errors()},
    )


# Include API v1 routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Report readiness of PostgreSQL and the configured MinIO bucket."""
    from app.services.health_service import readiness
    checks = await readiness()
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "unavailable", "checks": checks},
    )


if settings.ADMIN_ENABLED:
    from app.admin.app import create_admin_app
    app.mount("/admin", create_admin_app())
