import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.main import create_app
from app.settings import Settings


def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        encryption_key=SecretStr(Fernet.generate_key().decode()),
    )


@pytest.mark.asyncio
async def test_readiness_depends_on_database() -> None:
    async def unavailable() -> bool:
        return False

    app = create_app(settings(), db_probe=unavailable)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/internal/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert response.json()["artifact_service"] == "not_configured"
    await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_readiness_allows_missing_artifact_service() -> None:
    async def available() -> bool:
        return True

    app = create_app(settings(), db_probe=available)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/internal/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True
    await app.state.engine.dispose()
