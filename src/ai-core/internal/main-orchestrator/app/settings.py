from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    encryption_key: SecretStr
    worker_urls: dict[str, str] = Field(default_factory=dict)
    worker_timeout_seconds: int = Field(default=1800, ge=1, le=3600)
    min_input_url_ttl_seconds: int = Field(default=900, ge=1)
    artifact_service_url: str | None = None

    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_", extra="ignore")
