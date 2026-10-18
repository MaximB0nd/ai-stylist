import pytest

from .support import ARTIFACT_ID, expiry, image_bytes


def test_import_returns_readable_service_url_without_second_download(client):
    request = {
        "source_url": "http://source.test/photo",
        "max_size_bytes": 1024,
        "expires_at": expiry(),
    }
    first = client.post(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", json=request)
    assert first.status_code == 201, first.text
    assert first.json()["media_type"] == "image/png"
    assert first.json()["url"] == f"http://artifact.test/internal/v1/artifacts/{ARTIFACT_ID}/content"
    second = client.post(f"/internal/v1/artifacts/{ARTIFACT_ID}/content", json=request)
    assert second.status_code == 200, second.text
    assert len(client.source_calls) == 1
    read = client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content")
    assert read.status_code == 200
    assert read.content == image_bytes()

def test_old_import_route_is_removed(client):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/import",
        json={"source_url": "http://source.test/photo", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == 404
    assert client.source_calls == []

def test_rejects_other_import_origin_without_request(client):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/content",
        json={"source_url": "http://elsewhere.test/photo", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "SOURCE_URL_NOT_ALLOWED"
    assert client.source_calls == []

def test_rejects_redirect_from_source(client):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/content",
        json={"source_url": "http://source.test/redirect", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == 422
    assert len(client.source_calls) == 1

def test_invalid_source_port_is_rejected(client):
    response = client.post(
        f"/internal/v1/artifacts/{ARTIFACT_ID}/content",
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
        f"/internal/v1/artifacts/{ARTIFACT_ID}/content",
        json={"source_url": f"http://source.test/{path}", "max_size_bytes": 1024, "expires_at": expiry()},
    )
    assert response.status_code == status
    assert response.json()["code"] == code
    assert client.get(f"/internal/v1/artifacts/{ARTIFACT_ID}/content").status_code == 404
