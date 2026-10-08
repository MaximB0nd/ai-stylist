import json
import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from app.artifacts import ImportResult
from app.db import Command, Job
from app.dispatch import dispatch_one
from app.imports import process_one_import
from app.main import create_app
from app.schemas import JobCreate
from app.settings import Settings
from test_jobs_api import request_body

DATABASE_URL = os.getenv("ORCHESTRATOR_TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:55439/orchestrator_test")
STAGES = ("FACE_VALIDATION", "BODY_VALIDATION", "IDENTITY_VERIFICATION", "NORMALIZE_FACE",
          "NORMALIZE_BODY", "COLOR_TYPE", "STYLING", "GENERATION", "VERIFICATION")


class FakeArtifacts:
    def __init__(self):
        self.deleted = []

    async def import_file(self, artifact_id, source_url):
        return ImportResult(artifact_id=artifact_id, checksum_sha256="sha256:" + "a" * 64,
                            size_bytes=100, media_type="image/jpeg", width=512, height=768)

    async def access(self, artifact_id, operation, content_type="image/webp"):
        return {"artifact_id": artifact_id, "url": f"http://files.test/{operation}/{artifact_id}"}

    async def delete(self, artifact_id):
        self.deleted.append(artifact_id)


def metadata(media_type="image/png"):
    return {"checksum_sha256": "sha256:" + "b" * 64, "size_bytes": 100,
            "media_type": media_type, "width": 512, "height": 768}


@pytest.mark.asyncio
async def test_complete_pipeline_with_rejected_candidate_and_polling():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    app.state.artifacts = artifacts
    current = {"stage": None, "verifications": 0, "stylings": 0}
    sent = []

    def worker(request):
        body = json.loads(request.content)
        stage = current["stage"]
        sent.append((stage, request.url.path, body))
        if stage in ("FACE_VALIDATION", "BODY_VALIDATION"):
            result = {"decision": "ACCEPTED", "reasons": [], "model_version": "model-1",
                      "model_versions": {"person_detection": "model-1", "pose_estimation": "model-1"}}
        elif stage == "IDENTITY_VERIFICATION":
            result = {"decision": "SAME_PERSON", "model_versions": {"face_detector": "1", "face_recognizer": "1"}}
        elif stage in ("NORMALIZE_FACE", "NORMALIZE_BODY", "GENERATION"):
            artifact = metadata("image/webp" if stage == "GENERATION" else "image/png")
            if stage in ("NORMALIZE_FACE", "NORMALIZE_BODY"):
                artifact.update(width=body["output"]["width"], height=body["output"]["height"])
            result = {"artifact": artifact,
                      "model_version": "model-1", "prompt_version": "prompt-1"}
        elif stage == "COLOR_TYPE":
            result = {"color_type": "summer", "model_version": "color-1"}
        elif stage == "STYLING":
            current["stylings"] += 1
            result = {"outfit_spec_version": "1.0",
                      "outfit_spec": {"items": ["jacket" if current["stylings"] == 1 else "coat"]},
                      "model_version": "stylist-1", "prompt_version": "prompt-1"}
        else:
            current["verifications"] += 1
            result = {"verdict": "REJECTED" if current["verifications"] == 1 else "ACCEPTED",
                      "reason_codes": [], "policy_version": "1"}
        return httpx.Response(200, json={"request_id": body["request_id"], **result})

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=httpx.MockTransport(worker)) as worker_client:
            body = request_body()
            body["requested_image_count"] = 2
            body["request_hash"] = JobCreate.model_validate(body).computed_hash()
            created = await client.post("/internal/v1/jobs", json=body)
            assert created.status_code == 201
            job_id = created.json()["job_id"]
            assert await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            assert await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            expected = ["FACE_VALIDATION", "BODY_VALIDATION", "IDENTITY_VERIFICATION", "NORMALIZE_FACE",
                        "NORMALIZE_BODY", "COLOR_TYPE", "STYLING", "GENERATION", "VERIFICATION",
                        "GENERATION", "VERIFICATION", "STYLING", "GENERATION", "VERIFICATION"]
            for stage in expected:
                current["stage"] = stage
                assert await dispatch_one(app.state.sessions, app.state.cipher,
                                          {name: "https://worker.test" for name in STAGES},
                                          artifacts, worker_client, job_id)
            assert [stage for stage, _, _ in sent] == expected
            assert sent[0][1] == "/v1/validate"
            assert sent[3][2]["profile"] == "face"
            assert sent[4][2]["profile"] == "full_body"
            assert sent[6][2]["color_type"] == "summer"
            assert len(sent[11][2]["reserved_outfit_hashes"]) == 1
            assert sent[7][2]["output"]["write_url"].startswith("http://files.test/WRITE/")
            assert sent[7][2]["request_id"] != sent[9][2]["request_id"]
            got = await client.get(f"/internal/v1/jobs/{job_id}")
            assert got.status_code == 200, got.text
            view = got.json()
            assert view["status"] == "COMPLETED" and view["accepted_image_count"] == 2
            assert len(view["results"]) == 2
            assert view["results"][0]["download_url"].startswith("http://files.test/READ/")
            assert view["results"][0]["model_version"] == "model-1"
            async with app.state.sessions() as session:
                job = await session.get(Job, job_id)
                assert job.request_encrypted is None and job.color_type == "summer"
            assert (await client.post(f"/internal/v1/jobs/{job_id}/results/ack", json={})).status_code == 204
    finally:
        await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_face_rejection_stops_pipeline_with_reasons():
    app = create_app(Settings(database_url=DATABASE_URL, encryption_key=SecretStr(Fernet.generate_key().decode())))
    artifacts = FakeArtifacts()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "request_id": json.loads(request.content)["request_id"], "decision": "REJECTED",
        "reasons": ["FACE_TOO_BLURRY"], "model_version": "model-1"}))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client, \
                httpx.AsyncClient(transport=transport) as worker_client:
            job_id = (await client.post("/internal/v1/jobs", json=request_body())).json()["job_id"]
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await process_one_import(app.state.sessions, app.state.cipher, artifacts, job_id)
            await dispatch_one(app.state.sessions, app.state.cipher,
                               {"FACE_VALIDATION": "https://worker.test"}, artifacts, worker_client, job_id)
            view = (await client.get(f"/internal/v1/jobs/{job_id}")).json()
            assert view["status"] == "FAILED"
            assert view["error"]["code"] == "FACE_PHOTO_REJECTED"
            assert view["error"]["reasons"] == ["FACE_TOO_BLURRY"]
            async with app.state.sessions() as session:
                commands = (await session.execute(select(Command).where(Command.job_id == job_id))).scalars().all()
                assert len(commands) == 1
    finally:
        await app.state.engine.dispose()
