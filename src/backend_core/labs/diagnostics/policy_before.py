"""Distinguish temporary dependency outages from terminal delivery errors."""

import httpx
from minio.error import InvalidResponseError, S3Error, ServerError
from sqlalchemy.exc import SQLAlchemyError
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.services.ai_core_client import AICoreError


def is_retryable_ai_error(exc: Exception) -> bool:
    if isinstance(exc, AICoreError):
        return exc.status_code is None or exc.status_code == 429 or exc.status_code >= 500
    return isinstance(exc, (httpx.RequestError, OSError))


def is_retryable_delivery_error(exc: Exception) -> bool:
    if isinstance(exc, S3Error):
        status = getattr(exc.response, "status", None)
        return exc.code in {
            "SlowDown", "InternalError", "ServiceUnavailable", "RequestTimeout",
            "Throttling", "OperationAborted",
        } or status == 429 or (isinstance(status, int) and status >= 500)
    if isinstance(exc, ServerError):
        return exc.status_code == 429 or exc.status_code >= 500
    if isinstance(exc, InvalidResponseError):
        # The SDK exposes the HTTP code only in its stored constructor argument.
        status = exc._code
        return status == 429 or status >= 500
    return (
        is_retryable_ai_error(exc)
        or isinstance(exc, (Urllib3HTTPError, SQLAlchemyError))
        or (isinstance(exc, RuntimeError) and "HTTP 5" in str(exc))
    )


def retry_deadline(exc):
    """Honor integer Retry-After without blocking the recovery worker."""
    from datetime import datetime, timedelta, timezone
    from app.core.config import settings
    delay = max(settings.GENERATION_RECOVERY_INTERVAL_SECONDS,
                getattr(exc, "retry_after_seconds", None) or 0)
    return datetime.now(timezone.utc) + timedelta(seconds=delay)
