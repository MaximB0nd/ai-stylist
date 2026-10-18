import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    checksum_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    media_type: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ArtifactFailure(Exception):
    def __init__(self, code: str, retryable: bool, ambiguous: bool = False,
                 retry_after_seconds: int | None = None) -> None:
        self.code = code
        self.retryable = retryable
        self.ambiguous = ambiguous
        self.retry_after_seconds = retry_after_seconds
        super().__init__(code)


class ArtifactClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(timeout=120)

    async def import_file(self, artifact_id: str, source_url: str) -> ImportResult:
        try:
            response = await self.client.post(
                f"{self.base_url}/internal/v1/artifacts/{artifact_id}/import",
                json={
                    "source_url": source_url,
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
            try:
                retry_after = max(1, min(300, int(response.headers["Retry-After"])))
            except (KeyError, ValueError):
                retry_after = None
            raise ArtifactFailure(
                str(payload.get("code", "ARTIFACT_SERVICE_ERROR")),
                bool(payload.get("retryable", response.status_code >= 500)),
                retry_after_seconds=retry_after,
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
            body = {"operation": operation}
            if operation == "WRITE":
                body.update({"content_type": content_type, "max_size_bytes": 15728640})
            response = await self.client.post(f"{self.base_url}/internal/v1/artifacts/{artifact_id}/access", json=body)
            if response.status_code != 200:
                try:
                    problem = response.json()
                except ValueError:
                    problem = {}
                raise ArtifactFailure(str(problem.get("code", "ARTIFACT_SERVICE_ERROR")),
                                      bool(problem.get("retryable", response.status_code >= 500)))
            data = response.json()
            if data["artifact_id"] != artifact_id or not data["url"].startswith("http://"):
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
