from datetime import timedelta

from fastapi import FastAPI
from fastapi.responses import Response

from ..config import Settings
from ..storage import Storage
from .common import ArtifactError, check_id, utcnow


def register_lifecycle(app: FastAPI, settings: Settings, storage: Storage) -> None:
    @app.get("/internal/ready")
    async def ready():
        if not await storage.ready():
            raise ArtifactError(503, "STORAGE_UNAVAILABLE", retryable=True)
        return {"status": "ready"}

    @app.delete("/internal/v1/artifacts/{artifact_id}")
    async def delete_artifact(artifact_id: str):
        check_id(artifact_id)
        async with storage.lock:
            state = await storage.get_state(artifact_id)
            if state is None:
                state = {
                    "status": "DELETED",
                    "expires_at": (utcnow() + timedelta(seconds=settings.max_lifetime_seconds)).isoformat(),
                }
            else:
                state["status"] = "DELETED"
            await storage.put_state(artifact_id, state)
        if state.get("blob_key"):
            await storage.delete_object(state["blob_key"])
        return Response(status_code=204)
