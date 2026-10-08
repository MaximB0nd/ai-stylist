from datetime import datetime

import httpx
from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    checksum_sha256: str
    size_bytes: int
    format: str
    url: HttpUrl
    expires_at: datetime


class ArtifactFailure(Exception):
    def __init__(self, code: str, retryable: bool, ambiguous: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        self.ambiguous = ambiguous
        super().__init__(code)


class ArtifactClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(timeout=120)

    async def import_file(self, artifact_id: str, source_url: str, source_expires_at: datetime) -> ImportResult:
        try:
            response = await self.client.post(
                f"{self.base_url}/internal/v1/artifacts/{artifact_id}/import",
                json={
                    "source_url": source_url,
                    "source_expires_at": source_expires_at.isoformat(),
                    "max_size_bytes": 15728640,
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ArtifactFailure("SOURCE_UNAVAILABLE", True, ambiguous=True) from exc
        if response.status_code not in (200, 201):
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            raise ArtifactFailure(
                str(payload.get("code", "ARTIFACT_SERVICE_ERROR")),
                bool(payload.get("retryable", response.status_code >= 500)),
            )
        try:
            result = ImportResult.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ArtifactFailure("INVALID_ARTIFACT_RESPONSE", False) from exc
        if result.artifact_id != artifact_id:
            raise ArtifactFailure("ARTIFACT_ID_MISMATCH", False)
        return result

    async def access(self, artifact_id: str, operation: str, content_type: str = "image/webp") -> dict:
        try:
            response = await self.client.post(
                f"{self.base_url}/internal/v1/artifacts/{artifact_id}/access",
                json={"operation": operation, "content_type": content_type, "max_size_bytes": 15728640},
            )
            response.raise_for_status()
            data = response.json()
            if data["artifact_id"] != artifact_id or not data["url"].startswith("https://") or not data["expires_at"]:
                raise ValueError("Invalid access response")
            return data
        except httpx.HTTPError as exc:
            raise ArtifactFailure("ARTIFACT_SERVICE_ERROR", True, ambiguous=True) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactFailure("INVALID_ARTIFACT_RESPONSE", True) from exc

    async def delete(self, artifact_id: str) -> None:
        try:
            response = await self.client.delete(f"{self.base_url}/internal/v1/artifacts/{artifact_id}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ArtifactFailure("ARTIFACT_SERVICE_ERROR", True, ambiguous=True) from exc

    async def close(self) -> None:
        await self.client.aclose()
