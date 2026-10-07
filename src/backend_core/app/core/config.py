from pathlib import Path
from typing import Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

backend_core_env = Path(__file__).resolve().parent.parent.parent / ".env"


# Minimum lengths enforced by validators
# SECRET_KEY: >= 32 chars (JWT signing key must be strong)
# AI tokens: >= 24 chars (enough entropy for HMAC and bearer tokens)
_SECRET_KEY_MIN_LEN = 32
_AI_TOKEN_MIN_LEN = 24

# Values that are always rejected regardless of length
_FORBIDDEN_SECRETS: set[str] = {
    "changeme",
    "secret",
    "password",
    "test",
    "12345",
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


    # Database connection parameters (strictly required from .env / environment)
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Optional explicit database URL (if not provided, assembled safely via URL.create)
    DATABASE_URL: Optional[str] = None

    # MinIO / S3-compatible storage (strictly required from .env / environment)
    MINIO_ENDPOINT: str
    MINIO_PUBLIC_ENDPOINT: Optional[str] = None
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    MINIO_SECURE: bool = False
    MINIO_PUBLIC_SECURE: Optional[bool] = None
    MINIO_PRESIGNED_TTL: int = 3600  # presigned URL lifetime in seconds

    # AI Core Integration (strictly required from .env / environment)
    AI_CORE_URL: str
    AI_CORE_SERVICE_TOKEN: str
    AI_CORE_WEBHOOK_SECRET: str

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Reject trivially weak SECRET_KEY values and enforce minimum length."""
        if v.lower() in _FORBIDDEN_SECRETS:
            raise ValueError(
                f"SECRET_KEY '{v}' is trivially insecure. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if len(v) < _SECRET_KEY_MIN_LEN:
            raise ValueError(
                f"SECRET_KEY must be at least {_SECRET_KEY_MIN_LEN} characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("AI_CORE_SERVICE_TOKEN", "AI_CORE_WEBHOOK_SECRET", mode="after")
    @classmethod
    def validate_ai_secrets(cls, v: str) -> str:
        """Reject trivially weak AI Core tokens and enforce minimum length."""
        if v.lower() in _FORBIDDEN_SECRETS:
            raise ValueError(
                "AI Core secret token is trivially insecure — replace with a real secret."
            )
        if len(v) < _AI_TOKEN_MIN_LEN:
            raise ValueError(
                f"AI Core secret token must be at least {_AI_TOKEN_MIN_LEN} characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(24))\""
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
