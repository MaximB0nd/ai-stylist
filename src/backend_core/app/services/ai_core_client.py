"""HTTP client for interacting with AI Core service per public API contract."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Mapping from Backend Core situations to AI Core occasions
SITUATION_TO_OCCASION: Dict[str, str] = {
    "street": "casual",
    "study": "study",
    "office": "office",
    "evening": "evening",
}

# Mapping from Backend Core gender to AI Core gender
GENDER_MAP: Dict[str, str] = {
    "f": "female",
    "m": "male",
}


class AICoreError(Exception):
    """Base exception for AI Core communication errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


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
            "Authorization": f"Bearer {self.service_token}",
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
        description: Optional[str] = None,
        requested_image_count: int = 10,
    ) -> Dict[str, Any]:
        """Submit a new image generation job to AI Core (POST /v1/jobs)."""
        occasion = SITUATION_TO_OCCASION.get(situation, "casual")
        mapped_gender = GENDER_MAP.get(gender, "unspecified")

        payload = {
            "requested_image_count": requested_image_count,
            "inputs": {
                "face_photo_url": face_photo_url,
                "body_photo_url": body_photo_url,
                "expires_at": expires_at.isoformat(),
            },
            "person": {
                "age": age,
                "height_cm": height_cm,
                "gender": mapped_gender,
            },
            "preferences": {
                "occasion": occasion,
                "styles": styles,
                "shoes": shoes,
                "impressions": impressions,
                "description": description or f"Generation for {situation}",
            },
        }

        url = f"{self.base_url}/v1/jobs"
        headers = self._headers(idempotency_key=str(generation_id))

        try:
            async with self._get_client() as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code not in (200, 201, 202):
                    logger.error("AI Core create_job error [%s]: %s", resp.status_code, resp.text)
                    raise AICoreError(
                        f"AI Core rejected job: {resp.text}",
                        status_code=resp.status_code,
                        response_body=resp.text,
                    )
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
                    raise AICoreError(
                        f"Failed to fetch AI Core job {job_id}: {resp.text}",
                        status_code=resp.status_code,
                        response_body=resp.text,
                    )
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
                if resp.status_code not in (200, 204):
                    logger.error("AI Core ACK failed [%s]: %s", resp.status_code, resp.text)
                    raise AICoreError(
                        f"AI Core ACK rejected: {resp.text}",
                        status_code=resp.status_code,
                        response_body=resp.text,
                    )
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
                if resp.status_code not in (200, 204):
                    raise AICoreError(
                        f"Failed to cancel AI Core job {job_id}: {resp.text}",
                        status_code=resp.status_code,
                        response_body=resp.text,
                    )
                return resp.json() if resp.content else {"status": "CANCELLED"}
        except httpx.RequestError as exc:
            raise AICoreError(f"Network error cancelling AI Core job: {exc}") from exc
