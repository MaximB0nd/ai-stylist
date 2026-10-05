from contextlib import asynccontextmanager
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
        storage._ensure_bucket()
        logger.info("MinIO bucket '%s' ready.", storage.bucket)
    except Exception as e:
        logger.warning("Could not auto-create MinIO bucket on startup: %s", e)
    yield


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
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


# Include API v1 routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Basic service healthcheck endpoint."""
    return {"status": "ok"}
