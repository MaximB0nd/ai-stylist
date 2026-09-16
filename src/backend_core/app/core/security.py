from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


import asyncio
import logging

logger = logging.getLogger(__name__)


def _sync_hash_password(password: str) -> str:
    """Synchronous CPU-bound bcrypt hashing without silent truncation."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password cannot exceed 72 bytes in UTF-8 encoding.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def _sync_verify_password(plain_password: str, hashed_password: str) -> bool:
    """Synchronous CPU-bound bcrypt verification catching corrupted hashes."""
    try:
        plain_bytes = plain_password.encode("utf-8")
        if len(plain_bytes) > 72:
            return False
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except (ValueError, TypeError) as exc:
        logger.error("Corrupted or unsupported password hash format encountered: %s", exc)
        return False


async def hash_password(password: str) -> str:
    """Hash a password using bcrypt offloaded to a thread pool."""
    return await asyncio.to_thread(_sync_hash_password, password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against an existing bcrypt hash offloaded to a thread pool."""
    return await asyncio.to_thread(_sync_verify_password, plain_password, hashed_password)


def create_access_token(subject: str | uuid.UUID, expires_delta: timedelta | None = None) -> str:
    """Generate a signed JWT access token for the given subject."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token, returning its payload dict or None."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        return None
