# Local artifact service HTTP contract

## Deployment boundary

The service is one FastAPI serving process in a private local Docker Compose network.
SeaweedFS provides its S3-compatible bucket. No other AI Core service receives the
S3 endpoint or credentials. The service uses HTTP for this local version. There are
no separate authorization headers, secret capability URLs, or access-link endpoint.
Neither the service nor its management routes may be exposed publicly.

The caller creates a canonical, uppercase, 26-character ULID `artifact_id`. The
service never creates IDs or chooses an artifact's expiry. It does not own job
state or permanent product files.

## Import by URL

```http
POST /internal/v1/artifacts/{artifact_id}/content
Content-Type: application/json
```

```json
{
  "source_url": "http://source.test/photo",
  "max_size_bytes": 15728640,
  "expires_at": "2026-10-08T18:00:00Z"
}
```

The source URL must use HTTP and match the configured scheme, hostname, and port
exactly. A private destination is allowed only for that configured local origin.
Userinfo, fragments, redirects, and other origins are rejected. The source is
downloaded with GET without extra request headers. Separate connect, read, and
total timeouts apply. The service limits actual streamed bytes, regardless of
`Content-Length`.

First successful import returns `201`; an identical completed import returns
`200` without downloading again. Both return:

```json
{
  "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9B1",
  "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "media_type": "image/png",
  "size_bytes": 1048576,
  "width": 1536,
  "height": 2048,
  "url": "http://artifact-service/internal/v1/artifacts/01J8Z8Y7W6V5T4S3R2Q1P0N9B1/content"
}
```

The URL is an ordinary service URL derived from the ID. It has no independent
expiry. It stops working when the artifact expires or is deleted. The service
stores only a hash of the normalized import parameters, never the source URL.
A different import or another creation method for the same ID returns
`409 ARTIFACT_CONFLICT`.

## Direct write and read

The same `/internal/v1/artifacts/{artifact_id}/content` address accepts POST
for import, PUT for direct upload, and GET for reading. The former `/import`
address is not available.

```http
PUT /internal/v1/artifacts/{artifact_id}/content
Content-Type: image/png
X-Artifact-Expires-At: 2026-10-08T18:00:00Z

<raw image bytes>
```

The first PUT requires `X-Artifact-Expires-At`; a retry before publication uses
the same value and `Content-Type`. The artifact expiry must be future,
timezone-aware, and no more than 24 hours away. The accepted `Content-Type`
is `image/jpeg`, `image/png`, or `image/webp`, and must match the actual
signature. `multipart/form-data` is not accepted. A successful PUT returns
`204` only after technical verification and publication. A published object is
immutable; another PUT returns `409`.

```http
GET /internal/v1/artifacts/{artifact_id}/content
```

GET returns only published, unexpired objects, streamed from S3. It supports a
single valid `Range: bytes=...` request and returns `206` with
`Content-Range`; invalid or out-of-bounds ranges return `416`. Missing,
deleted, or expired objects return `404`. Responses use `Cache-Control:
no-store`.

## Technical image checks

For import and PUT, the service accepts JPEG, PNG, and WebP, at most 15 MiB,
4096 pixels per dimension, 4096 × 4096 pixels total, one frame, and eight
bits per channel. It bounds EXIF and ICC data to 1 MiB each, parses them
safely, and decodes the image before publication. These limits are deployment
settings. The service does not change pixels, metadata, or color profiles and
does not evaluate whether the photo is suitable for an ML task.

Bytes first enter an S3 staging object. A small S3 control object records the
artifact expiry, status, and published object key. Only the control object
can make bytes readable through the service. Failed transfers remove staging
bytes. No transfer is persisted on the service's local filesystem.

## Delete and readiness

```http
DELETE /internal/v1/artifacts/{artifact_id}
GET /internal/ready
```

DELETE returns `204`, including for an absent or already deleted artifact.
It durably marks the ID deleted before deleting bytes. A concurrent or late
PUT/import cannot publish after this mark, including across a process restart.
This local guarantee assumes exactly one serving process. The deployment must
not run multiple replicas or Uvicorn workers.

Ready returns `200` when configuration is valid and the S3 bucket is
reachable; otherwise it returns `503`.

## Errors

Errors use `application/problem+json` with `type`, `title`, `status`,
`code`, and `retryable`. Malformed JSON returns `400 MALFORMED_REQUEST`;
schema and ULID errors return `422 VALIDATION_ERROR`. The service uses
`409` for conflicting creation, active transfers, and writes to a closed
object; `413` for an oversized PUT; `415` for unsupported PUT content type;
and `416` for invalid ranges. Source failures distinguish inaccessible
(`422`), unavailable (`502`), and timeout (`504`) responses. Errors do
not include source URLs, image bytes, internal S3 keys, or S3 responses.
