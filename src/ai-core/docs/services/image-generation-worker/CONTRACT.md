# Договор воркера генерации изображения

## Очереди

- команды: `ai.worker.image.generate.commands`;
- результаты: `ai.worker.image.generate.results`.

Сообщение использует [общую оболочку](../../message-contracts.md).

## Полезная нагрузка команды

```json
{
  "face_photo_url": "https://storage.example/prepared-face",
  "body_photo_url": "https://storage.example/prepared-body",
  "outfit_spec": {
    "schema_version": "1.0",
    "outfit_id": "f883f0d6-61bf-432d-9bed-074d912db2f0",
    "items": []
  },
  "output_url": "https://storage.example/temporary-output",
  "model_version": "image-model@example",
  "prompt_version": "photographer-v1",
  "seed": 12345
}
```

## Полезная нагрузка успешного результата

```json
{
  "status": "SUCCEEDED",
  "object_key": "temporary/job-id/3/2/candidate.webp",
  "checksum_sha256": "sha256:example",
  "width": 1024,
  "height": 1536,
  "model_version": "image-model@example",
  "prompt_version": "photographer-v1",
  "seed": 12345
}
```

Окончательные коды ошибок: `INVALID_OUTFIT_SPEC`, `UNSUPPORTED_MODEL`. Временные:
`MODEL_UNAVAILABLE`, `OUT_OF_MEMORY`, `STORAGE_UNAVAILABLE`. Технический повтор
пишет по тому же `output_url`; новую модельную попытку создаёт только главный
оркестратор.
