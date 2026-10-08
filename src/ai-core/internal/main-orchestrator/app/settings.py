from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    encryption_key: SecretStr
    worker_urls: dict[str, str] = Field(default_factory=dict)
    artifact_service_url: str | None = None

    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_", extra="ignore")
