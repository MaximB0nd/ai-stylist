# Договор воркера подготовки

Имена очередей и оболочка сообщения определены в
[реестре сообщений](../../../messaging.md#очереди-воркеров).

## Команда

| Поле | Тип |
| --- | --- |
| `inputs` | Объект `inputs` из [публичного создания задания](../../../../public/ai-core-api/CONTRACT.md#создание-задания) |
| `face_output` | Объект с готовой `write_url`, `artifact_id` и `expires_at` |
| `body_output` | Объект с готовой `write_url`, `artifact_id` и `expires_at` |
| `max_file_size_bytes` | Положительное целое |
| `allowed_formats` | Непустой список форматов |

## Результат

```json
{
  "status": "SUCCEEDED",
  "face": {
    "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9A1",
    "checksum_sha256": "sha256:face",
    "size_bytes": 524288,
    "width": 1024,
    "height": 1024,
    "format": "webp"
  },
  "body": {
    "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9A2",
    "checksum_sha256": "sha256:body",
    "size_bytes": 786432,
    "width": 1024,
    "height": 1536,
    "format": "webp"
  }
}
```

Окончательные ошибки: `UNSUPPORTED_FORMAT`, `FILE_TOO_LARGE`, `INVALID_IMAGE`,
`UNSAFE_INPUT`. Временные ошибки: `INPUT_UNAVAILABLE`, `OUTPUT_UNAVAILABLE`.
