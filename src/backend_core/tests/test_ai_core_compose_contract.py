from pathlib import Path


COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.ai-core.yml"


def test_ai_core_overlay_uses_current_public_api_environment_contract() -> None:
    compose = COMPOSE.read_text()

    assert "PUBLIC_API_ORCHESTRATOR_URL:" in compose
    assert "PUBLIC_API_INPUT_ORIGINS:" in compose
    assert "PUBLIC_API_MIN_INPUT_URL_TTL_SECONDS:" in compose
    assert "AI_CORE_API_ORCHESTRATOR_URL:" not in compose
    assert "AI_CORE_API_INPUT_ORIGINS:" not in compose


def test_ai_core_overlay_configures_all_artifact_origins() -> None:
    compose = COMPOSE.read_text()

    assert "ORCHESTRATOR_ARTIFACT_SERVICE_URL:" in compose
    assert "ORCHESTRATOR_ARTIFACT_PUBLIC_BASE_URL:" in compose
    assert "ORCHESTRATOR_ARTIFACT_WORKER_BASE_URL:" in compose
