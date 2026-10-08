import asyncio
import json
from datetime import datetime, timedelta, timezone

from .support import ARTIFACT_ID, expiry, image_bytes


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
