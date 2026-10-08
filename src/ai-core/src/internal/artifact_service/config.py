from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARTIFACT_", extra="ignore")

    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    bucket: str = "artifacts"
    source_origin: str
    public_base_url: str
    max_size_bytes: int = Field(default=15 * 1024 * 1024, gt=0)
    max_lifetime_seconds: int = Field(default=24 * 60 * 60, gt=0)
    max_dimension: int = Field(default=4096, gt=0)
    max_exif_bytes: int = Field(default=1024 * 1024, gt=0)
    max_icc_bytes: int = Field(default=1024 * 1024, gt=0)
    cleanup_interval_seconds: int = Field(default=3600, gt=0)

    @field_validator("source_origin", "public_base_url")
    @classmethod
    def local_http_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("must be an HTTP origin without credentials, query, or fragment")
        if parsed.path not in ("", "/"):
            raise ValueError("must be an origin without a path")
        parsed.port
        return value.rstrip("/")
