from botocore.exceptions import ClientError

from .support import ARTIFACT_ID, expiry, image_bytes


def test_delete_before_put_prevents_creation(client):
    assert client.delete(f"/internal/v1/artifacts/{ARTIFACT_ID}").status_code == 204
    headers = {"Content-Type": "image/png", "X-Artifact-Expires-At": expiry()}
    assert client.put(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", content=image_bytes(), headers=headers).status_code == 409

def test_readiness_fails_when_bucket_is_missing(client):
    assert client.get("/internal/ready").status_code == 200
    client.storage.client.delete_bucket(Bucket=client.storage.settings.bucket)
    response = client.get("/internal/ready")
    assert response.status_code == 503

def test_s3_failure_is_reported_without_storage_details(client, monkeypatch):
    def fail(**_kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "secret bucket detail"}}, "GetObject")

    monkeypatch.setattr(client.storage.client, "get_object", fail)
    response = client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content")
    assert response.status_code == 502
    assert response.json()["code"] == "STORAGE_UNAVAILABLE"
    assert "secret bucket detail" not in response.text
