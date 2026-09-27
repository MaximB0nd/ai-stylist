# Договор воркера подготовки

Оболочка и очереди: [messaging.md](../../messaging.md).

## Команда

| Поле | Значение |
| --- | --- |
| `inputs` | объект из [создания задания](../../../public/ai-core-api/CONTRACT.md#создание-задания) |
| `face_output` | `artifact_id`, `write_url`, `expires_at` |
| `body_output` | `artifact_id`, `write_url`, `expires_at` |
| `max_file_size_bytes` | положительное целое |
| `allowed_formats` | непустой список |

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

| Код | Повтор |
| --- | --- |
| `UNSUPPORTED_FORMAT`, `FILE_TOO_LARGE`, `INVALID_IMAGE`, `UNSAFE_INPUT` | нет |
| `INPUT_UNAVAILABLE`, `OUTPUT_UNAVAILABLE` | да |

Ошибка и отмена: [общий результат](../../messaging.md#результат-воркера).
