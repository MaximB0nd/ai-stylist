from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

backend_core_env = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Stylist Backend Core"
    API_V1_PREFIX: str = "/api/v1"

    # JWT & Security (loaded from .env or environment variable)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stylist"

    model_config = SettingsConfigDict(
        env_file=(".env", str(backend_core_env)),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
