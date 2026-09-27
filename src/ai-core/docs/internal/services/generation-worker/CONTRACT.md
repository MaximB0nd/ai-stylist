# Договор воркера генерации

Оболочка и очереди: [messaging.md](../../messaging.md).

## Команда

| Поле | Значение |
| --- | --- |
| `prepared_inputs` | `face` и `body`: `artifact_id`, `read_url`, `expires_at`, метаданные |
| `outfit_spec` | [`OutfitSpec`](../../models.md#outfitspec-версии-1) |
| `output` | `artifact_id`, `write_url`, `expires_at` |
| `model_version` | точная версия |
| `prompt_version` | точная версия |
| `seed` | целое число |

Ссылки: [artifacts.md](../../artifacts.md#доступ).

## Результат

```json
{
  "status": "SUCCEEDED",
  "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9B1",
  "checksum_sha256": "sha256:example",
  "size_bytes": 1048576,
  "format": "webp",
  "width": 1024,
  "height": 1536,
  "model_version": "image-model@example",
  "prompt_version": "photographer-v1",
  "seed": 12345
}
```

| Код | Повтор |
| --- | --- |
| `INVALID_OUTFIT_SPEC`, `UNSUPPORTED_MODEL` | нет |
| `MODEL_UNAVAILABLE`, `OUT_OF_MEMORY`, `INPUT_UNAVAILABLE`, `OUTPUT_UNAVAILABLE` | да |

Ошибка и отмена: [общий результат](../../messaging.md#результат-воркера).
