5. AI Module Webhook Callback (AI Module $\rightarrow$ Core Backend)

Internal webhook invoked by the AI module to report generation completion, providing the MinIO object keys of all 10 generated looks.

Method: POST

URL: /api/v1/internal/generations/{generation_id}/complete

Headers:
- Content-Type: application/json
- X-Internal-Token: <internal_service_secret>

Request Body

```JSON
{
  "generation_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "COMPLETED",
  "photos": [
    {"order_index": 0, "object_key": "albums/3fa85f64/look_00.webp"},
    {"order_index": 1, "object_key": "albums/3fa85f64/look_01.webp"},
    {"order_index": 2, "object_key": "albums/3fa85f64/look_02.webp"},
    {"order_index": 3, "object_key": "albums/3fa85f64/look_03.webp"},
    {"order_index": 4, "object_key": "albums/3fa85f64/look_04.webp"},
    {"order_index": 5, "object_key": "albums/3fa85f64/look_05.webp"},
    {"order_index": 6, "object_key": "albums/3fa85f64/look_06.webp"},
    {"order_index": 7, "object_key": "albums/3fa85f64/look_07.webp"},
    {"order_index": 8, "object_key": "albums/3fa85f64/look_08.webp"},
    {"order_index": 9, "object_key": "albums/3fa85f64/look_09.webp"}
  ]
}
```

Responses

200 OK

```JSON
{
  "success": true,
  "album_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

404 Not Found — Unknown or invalid generation_id.
