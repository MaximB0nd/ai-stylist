import boto3
import httpx
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from internal.artifact_service.app import create_app
from internal.artifact_service.config import Settings
from internal.artifact_service.storage import Storage

from .support import image_bytes


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
