# Local artifact service

One FastAPI process stores temporary images in a private SeaweedFS S3 bucket.
The HTTP contract is documented in
[CONTRACT.md](../../../docs/internal/services/artifact-service/CONTRACT.md).
This Compose setup is for local development on a trusted machine only.

## Start

From the repository root:

```sh
docker compose --env-file src/ai-core/src/internal/artifact_service/.env.example \
  -f src/ai-core/src/internal/artifact_service/compose.yaml up -d --build
curl http://127.0.0.1:18081/internal/ready
```

SeaweedFS S3 is bound to `127.0.0.1:18333`; artifact HTTP is bound to
`127.0.0.1:18081`. The example credentials are only for local development.
For a reachable import source, set `ARTIFACT_SOURCE_ORIGIN` to exactly one HTTP
origin accessible from the Compose network, such as a local test server.
The source URL supplied to `POST /internal/v1/artifacts/{artifact_id}/content`
must match that origin and may include a path and query. Redirects are refused.
Tests use an in-process HTTP source;
the Compose stack intentionally has no always-running mock source.

The service creates its `artifacts` bucket at startup. The caller supplies a
canonical uppercase ULID. Import requires `source_url`, `max_size_bytes`, and
`expires_at`. For direct upload, the first PUT requires `Content-Type` and
`X-Artifact-Expires-At`. Import returns metadata and the ordinary HTTP content
URL. GET and PUT use the same URL. There are no access tokens or link expiry;
every client that can reach this local service and knows an ID can access its
file until the artifact expires or is deleted.

Run the unit tests with:

```sh
uv run --project src/ai-core --extra test python -m pytest src/ai-core/tests/artifact_service/test_image.py src/ai-core/tests/artifact_service/test_http.py -q
```

For real SeaweedFS integration tests, start `s3` with Compose, export the
values from `.env.example`, set
`ARTIFACT_S3_ENDPOINT=http://127.0.0.1:18333`, then run
`uv run --project src/ai-core --extra test python -m pytest src/ai-core/tests/artifact_service/test_s3_integration.py -q`.

Expired artifacts are hidden immediately and physically removed by the
background sweep (default hourly) or the next startup sweep. The serving
process must run with one Uvicorn worker and one Compose replica because the
transfer lock is process-local. S3 control objects retain deletion markers
until the artifact expiry; this prevents a late transfer from publishing after
DELETE across process restarts.
