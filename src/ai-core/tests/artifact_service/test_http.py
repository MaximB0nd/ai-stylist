import asyncio
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

import boto3
import httpx
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from moto import mock_aws
from PIL import Image

from internal.artifact_service.app import create_app
from internal.artifact_service.config import Settings
from internal.artifact_service.storage import Storage


ARTIFACT_ID = "01J8Z8Y7W6V5T4S3R2Q1P0N9B1"


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (3, 2), "red").save(output, format="PNG")
    return output.getvalue()


def expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


@pytest.fixture
def client():
    with mock_aws():
        settings = Settings(
            s3_endpoint="http://s3.test:8333",
            s3_access_key="test",
            s3_secret_key="test",
            source_origin="http://source.test",
            public_base_url="http://artifact.test",
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        storage = Storage(settings, client=s3)
        source_calls = []

        def source(request: httpx.Request):
            source_calls.append(request.url)
            if request.url.path == "/redirect":
                return httpx.Response(302, headers={"Location": "http://elsewhere.test/photo"})
            if request.url.path == "/missing":
                return httpx.Response(404)
            if request.url.path == "/unavailable":
                return httpx.Response(503)
            return httpx.Response(200, content=image_bytes(), headers={"Content-Type": "image/png"})

        app = create_app(settings, storage, httpx.MockTransport(source))
        with TestClient(app) as test_client:
            test_client.storage = storage
            test_client.source_calls = source_calls
            yield test_client


def test_import_returns_readable_service_url_without_second_download(client):
    request = {
        "source_url": "http://source.test/photo",
        "max_size_bytes": 1024,
        "expires_at": expiry(),
    }
    first = client.post(f"/internal/v1/artifacts/{ARTIFACT_ID}/import", json=request)
    assert first.status_code == 201, first.text
    assert first.json()["media_type"] == "image/png"
    assert first.json()["url"] == f"http://artifact.test/internal/v1/artifacts/{ARTIFACT_ID}/content"
    second = client.post(f"/internal/v1/artifacts/{ARTIFACT_ID}/import", json=request)
    assert second.status_code == 200, second.text
    assert len(client.source_calls) == 1
    read = client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content")
    assert read.status_code == 200
    assert read.content == image_bytes()


def test_put_then_read_range_and_delete(client):
    body = image_bytes()
    headers = {"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()}
    written = client.put(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", content=body, headers=headers)
    assert written.status_code == 204, written.text
    partial = client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", headers={"Range": "bytes=0-3"})
    assert partial.status_code == 206
    assert partial.content == body[:4]
    assert client.delete(f"/internal/v1/artifacts/{ARTIFACT_ID}").status_code == 204
    assert client.delete(f"/internal/v1/artifacts/{ARTIFACT_ID}").status_code == 204
    assert client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content").status_code == 404
    assert client.put(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", content=body, headers=headers).status_code == 409


def test_rejects_other_import_origin_without_request(client):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/import",
        json={"source_url": "http://elsewhere.test/photo", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SOURCE_URL_NOT_ALLOWED"
    assert client.source_calls == []


def test_rejects_redirect_from_source(client):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/import",
        json={"source_url": "http://source.test/redirect", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == 422
    assert len(client.source_calls) == 1


def test_failed_put_is_not_readable_and_can_be_retried(client):
    headers = {"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()}
    response = client.put(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", content=b"invalid", headers=headers)
    assert response.status_code == 422
    assert client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content").status_code == 404
    retry = client.put(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", content=image_bytes(), headers=headers)
    assert retry.status_code == 204


def test_rejects_oversized_put_and_bad_range(client):
    headers = {"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()}
    response = client.put(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/content",
        content=b"x" * (15 * 1024 * 1024 + 1),
        headers=headers,
    )
    assert response.status_code == 413
    assert client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content").status_code == 404
    assert client.put(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", content=image_bytes(), headers=headers).status_code == 204
    assert client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", headers={"Range": "bytes=999-"}).status_code == 416


def test_delete_before_put_prevents_creation(client):
    assert client.delete(f"/internal/v1/artifacts/{ARTIFACT_ID}").status_code == 204
    headers = {"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()}
    assert client.put(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", content=image_bytes(), headers=headers).status_code == 409


def test_put_requires_expiry_and_matching_image_type(client):
    url = f"/internal/v1/artifacts/{ARTIFACT_ID}/content"
    assert client.put(url, content=image_bytes(), headers={"Content-Type": "image/png"}).status_code == 422
    assert client.put(url, content=image_bytes(), headers={"Content-Type": "image/jpeg", "X-Artifact-Expires-At": expiry()}).status_code == 422
    assert client.get(url).status_code == 404


def test_empty_put_is_a_validation_error(client):
    response = client.put(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/content",
        content=b"",
        headers={"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNPROCESSABLE_IMAGE"


def test_expired_artifact_is_unreadable_and_cannot_be_overwritten(client):
    url = f"/internal/v1/artifacts/{ARTIFACT_ID}/content"
    headers = {"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()}
    assert client.put(url, content=image_bytes(), headers=headers).status_code == 204
    state = client.storage.client.get_object(Bucket=client.storage.settings.bucket, Key=client.storage.state_key(ARTIFACT_ID))
    saved = json.loads(state["Body"].read())
    saved["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    asyncio.run(client.storage.put_state(ARTIFACT_ID, saved))
    assert client.get(url).status_code == 404
    assert client.put(url, content=image_bytes(), headers=headers).status_code == 409


def test_readiness_fails_when_bucket_is_missing(client):
    assert client.get("/internal/ready").status_code == 200
    client.storage.client.delete_bucket(Bucket=client.storage.settings.bucket)
    response = client.get("/internal/ready")
    assert response.status_code == 503


def test_invalid_source_port_is_rejected(client):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/import",
        json={"source_url": "http://source.test:bad/photo", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SOURCE_URL_NOT_ALLOWED"


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [("missing", 422, "SOURCE_NOT_ACCESSIBLE"), ("unavailable", 502, "SOURCE_UNAVAILABLE")],
)
def test_source_error_does_not_publish(client, path, status, code):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/import",
        json={"source_url": f"http://source.test/{path}", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == status
    assert response.json()["code"] == code
    assert client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content").status_code == 404


def test_s3_failure_is_reported_without_storage_details(client, monkeypatch):
    def fail(**_kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "secret bucket detail"}}, "GetObject")

    monkeypatch.setattr(client.storage.client, "get_object", fail)
    response = client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content")
    assert response.status_code == 502
    assert response.json()["code"] == "STORAGE_UNAVAILABLE"
    assert "secret bucket detail" not in response.text
