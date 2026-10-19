"""HTTP client for interacting with AI Core service per public API contract."""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit
import uuid

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# REST keeps the historical minimalism spelling as an alias.
STYLE_MAP = {"minimalism": "minimal", "minimal": "minimal", "classic": "classic",
             "casual": "casual", "romantic": "romantic"}
GENDER_MAP = {"f": "female", "m": "male"}


def _single_choice(values, allowed, field):
    if len(values) != 1 or values[0] not in allowed:
        raise AICoreError(f"Unsupported {field}; exactly one supported value is required", status_code=400)
    return values[0]


class AICoreError(Exception):
    """Base exception for AI Core communication errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.retry_after_seconds = None

    @classmethod
    def from_response(cls, response):
        error = cls(f"AI Core HTTP {response.status_code}", response.status_code, response.text)
        value = response.headers.get("Retry-After", "").strip()
        if value.isascii() and value.isdigit() and len(value) <= 8:
            error.retry_after_seconds = int(value)
        return error


from contextlib import asynccontextmanager


class AICoreClient:
    """Async HTTP client implementing the AI Core public API contract."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        service_token: Optional[str] = None,
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = (base_url or settings.AI_CORE_URL).rstrip("/")
        self.service_token = service_token or settings.AI_CORE_SERVICE_TOKEN
        self.timeout = timeout
        self._client = client

    @asynccontextmanager
    async def _get_client(self):
        if self._client is not None:
            yield self._client
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                yield client

    def _headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def create_job(
        self,
        generation_id: uuid.UUID,
        face_photo_url: str,
        body_photo_url: str,
        expires_at: datetime,
        age: int,
        height_cm: int,
        gender: str,
        situation: str,
        styles: List[str],
        shoes: List[str],
        impressions: List[str],
        requested_image_count: int = 5,
    ) -> Dict[str, Any]:
        """Submit a new image generation job to AI Core (POST /v1/jobs)."""
        for url in (face_photo_url, body_photo_url):
            parsed = urlsplit(url)
            if (
                len(url) > 4096 or parsed.scheme != "http" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None or parsed.fragment
            ):
                raise AICoreError("Unsupported input URL", status_code=422)
        if (
            type(age) is not int or not 1 <= age <= 120
            or type(height_cm) is not int or not 80 <= height_cm <= 240
        ):
            raise AICoreError("Person values are outside the AI Core contract", status_code=400)
        style = _single_choice(styles, STYLE_MAP, "style")
        shoe = _single_choice(shoes, {"sneakers", "loafers", "heels", "boots"}, "shoe")
        mood = _single_choice(impressions, {"confident", "elegant", "relaxed", "bright"}, "mood")
        if situation not in {"street", "study", "office", "evening"} or gender not in GENDER_MAP:
            raise AICoreError("Unsupported occasion or gender", status_code=400)
        if type(requested_image_count) is not int or not 1 <= requested_image_count <= 10:
            raise AICoreError("requested_image_count must be an integer from 1 to 10", status_code=400)
        payload = {
            "requested_image_count": requested_image_count,
            "inputs": {
                "face": {"url": face_photo_url, "expires_at": expires_at.isoformat()},
                "body": {"url": body_photo_url, "expires_at": expires_at.isoformat()},
            },
            "person": {"age": age, "height_cm": height_cm, "gender": GENDER_MAP[gender]},
            "preferences": {"occasion": situation, "style": STYLE_MAP[style], "shoe": shoe, "mood": mood},
        }

        url = f"{self.base_url}/v1/jobs"
        headers = self._headers(idempotency_key=str(generation_id))

        try:
            async with self._get_client() as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code not in (200, 201):
                    logger.error("AI Core create_job error [%s]: %s", resp.status_code, resp.text)
                    raise AICoreError.from_response(resp)
                return resp.json()
        except httpx.RequestError as exc:
            logger.exception("Network error connecting to AI Core at %s", url)
            raise AICoreError(f"Network error communicating with AI Core: {exc}") from exc

    async def get_job(self, job_id: uuid.UUID | str) -> Dict[str, Any]:
        """Get status and results of a job (GET /v1/jobs/{job_id})."""
        url = f"{self.base_url}/v1/jobs/{job_id}"
        headers = self._headers()

        try:
            async with self._get_client() as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    raise AICoreError.from_response(resp)
                return resp.json()
        except httpx.RequestError as exc:
            raise AICoreError(f"Network error communicating with AI Core: {exc}") from exc

    async def acknowledge_results(self, job_id: uuid.UUID | str) -> bool:
        """Acknowledge download of generated photos (POST /v1/jobs/{job_id}/results/ack)."""
        url = f"{self.base_url}/v1/jobs/{job_id}/results/ack"
        headers = self._headers()

        try:
            async with self._get_client() as client:
                resp = await client.post(url, headers=headers)
                if resp.status_code != 204:
                    logger.error("AI Core ACK failed [%s]: %s", resp.status_code, resp.text)
                    raise AICoreError.from_response(resp)
                return True
        except httpx.RequestError as exc:
            raise AICoreError(f"Network error acknowledging AI Core job: {exc}") from exc

    async def cancel_job(self, job_id: uuid.UUID | str) -> Dict[str, Any]:
        """Cancel an in-progress job (POST /v1/jobs/{job_id}/cancel)."""
        url = f"{self.base_url}/v1/jobs/{job_id}/cancel"
        headers = self._headers()

        try:
            async with self._get_client() as client:
                resp = await client.post(url, headers=headers)
                if resp.status_code != 200:
                    raise AICoreError.from_response(resp)
                return resp.json() if resp.content else {"status": "CANCELLED"}
        except httpx.RequestError as exc:
            raise AICoreError(f"Network error cancelling AI Core job: {exc}") from exc
