# Договор воркера генерации

Имена очередей и оболочка сообщения определены в
[реестре сообщений](../../../messaging.md#очереди-воркеров). Поле `outfit_spec`
соответствует единственной схеме
[`OutfitSpec`](../../../models.md#outfitspec-версии-1).

## Команда

| Поле | Тип |
| --- | --- |
| `prepared_inputs` | Объект `face` и `body`; каждый содержит `artifact_id`, короткую `read_url`, `expires_at`, контрольную сумму, размер и формат |
| `outfit_spec` | [`OutfitSpec`](../../../models.md#outfitspec-версии-1) |
| `output` | Объект с готовой `write_url`, `artifact_id` и `expires_at`; отдельный для каждой попытки |
| `model_version` | Строка точной версии |
| `prompt_version` | Строка точной версии |
| `seed` | Целое число |

Смысл и срок файловых ссылок определены только в
[правилах временных файлов](../../../artifacts.md#запись-и-чтение).

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

Окончательные ошибки: `INVALID_OUTFIT_SPEC`, `UNSUPPORTED_MODEL`. Временные:
`MODEL_UNAVAILABLE`, `OUT_OF_MEMORY`, `INPUT_UNAVAILABLE`, `OUTPUT_UNAVAILABLE`.
