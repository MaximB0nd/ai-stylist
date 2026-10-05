from pathlib import Path
from typing import Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

backend_core_env = Path(__file__).resolve().parent.parent.parent / ".env"


# Weak/default secrets that must NOT be used in production
_FORBIDDEN_SECRETS: set[str] = {
    "temporary-secret-key-for-dev-change-in-prod",
    "temporary-ai-core-service-token",
    "temporary-ai-core-webhook-secret",
    "changeme",
    "secret",
    "password",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Stylist Backend Core"
    API_V1_PREFIX: str = "/api/v1"

    # Runtime environment: "development" | "staging" | "production"
    ENVIRONMENT: str = "development"

    # JWT & Security (loaded from .env or environment variable)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # CORS origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:8080",
        "http://localhost:5091",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5091",
        "http://127.0.0.1:3000",
    ]


    # Database connection parameters
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "stylist"

    # Optional explicit database URL (if not provided, assembled safely via URL.create)
    DATABASE_URL: Optional[str] = None

    # MinIO / S3-compatible storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_ENDPOINT: Optional[str] = None
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "stylist"
    MINIO_SECURE: bool = False
    MINIO_PUBLIC_SECURE: Optional[bool] = None
    MINIO_PRESIGNED_TTL: int = 3600  # presigned URL lifetime in seconds


    # AI Core Integration
    AI_CORE_URL: str = "http://localhost:8001"
    AI_CORE_SERVICE_TOKEN: str = "temporary-ai-core-service-token"
    AI_CORE_WEBHOOK_SECRET: str = "temporary-ai-core-webhook-secret"

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Reject weak/default SECRET_KEY values and enforce minimum length."""
        if v.lower() in _FORBIDDEN_SECRETS or len(v) < 32:
            raise ValueError(
                "SECRET_KEY is insecure: use a strong random value of at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("AI_CORE_SERVICE_TOKEN", "AI_CORE_WEBHOOK_SECRET", mode="after")
    @classmethod
    def validate_ai_secrets(cls, v: str) -> str:
        """Reject default AI Core tokens."""
        if v.lower() in _FORBIDDEN_SECRETS:
            raise ValueError(
                f"AI Core secret token is insecure — replace the default value in your environment."
            )
        return v

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = URL.create(
                drivername="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                database=self.POSTGRES_DB,
            ).render_as_string(hide_password=False)
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", str(backend_core_env)),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
