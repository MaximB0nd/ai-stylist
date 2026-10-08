import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from ..config import Settings


ULID = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str
    max_size_bytes: int = Field(gt=0)
    expires_at: datetime


class ArtifactError(Exception):
    def __init__(self, status: int, code: str, *, retryable: bool = False, retry_after: int | None = None):
        self.status = status
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_expiry(value: datetime, settings: Settings) -> str:
    now = utcnow()
    if value.tzinfo is None or not (now < value <= now + timedelta(seconds=settings.max_lifetime_seconds)):
        raise ArtifactError(422, "VALIDATION_ERROR")
    return value.astimezone(timezone.utc).isoformat()


def not_expired(state: dict) -> bool:
    return datetime.fromisoformat(state["expires_at"]) > utcnow()


def check_id(artifact_id: str) -> None:
    if not ULID.fullmatch(artifact_id):
        raise ArtifactError(422, "VALIDATION_ERROR")


def validate_source_url(source_url: str, origin: str) -> None:
    try:
        parsed = urlsplit(source_url)
        allowed = urlsplit(origin)
        valid = (
            parsed.scheme == "http"
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and bool(parsed.hostname)
            and (parsed.scheme, parsed.hostname.lower(), parsed.port or 80)
            == (allowed.scheme, allowed.hostname.lower(), allowed.port or 80)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ArtifactError(422, "SOURCE_URL_NOT_ALLOWED")


def parse_range(value: str | None, size: int) -> tuple[str | None, int, int]:
    if value is None:
        return None, 0, size - 1
    match = RANGE.fullmatch(value)
    if not match or not any(match.groups()) or size < 1:
        raise ArtifactError(416, "INVALID_RANGE")
    first, last = match.groups()
    if first:
        start = int(first)
        end = int(last) if last else size - 1
    else:
        count = int(last)
        if count == 0:
            raise ArtifactError(416, "INVALID_RANGE")
        start = max(0, size - count)
        end = size - 1
    if start >= size or end < start:
        raise ArtifactError(416, "INVALID_RANGE")
    end = min(end, size - 1)
    return f"bytes={start}-{end}", start, end
