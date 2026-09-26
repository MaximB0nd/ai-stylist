# Договор воркера подготовки фотографий

## Очереди

- команды: `ai.worker.photo.prepare.commands`;
- результаты: `ai.worker.photo.prepare.results`.

Сообщение использует [общую оболочку](../../message-contracts.md).

## Полезная нагрузка команды

```json
{
  "face_photo_url": "https://storage.example/temporary-face",
  "body_photo_url": "https://storage.example/temporary-body",
  "output_prefix": "temporary/job-id/prepared/",
  "max_file_size_bytes": 20971520,
  "allowed_formats": ["jpeg", "png", "webp"]
}
```

## Полезная нагрузка успешного результата

```json
{
  "status": "SUCCEEDED",
  "face_object_key": "temporary/job-id/prepared/face.webp",
  "body_object_key": "temporary/job-id/prepared/body.webp",
  "width": 1024,
  "height": 1536,
  "format": "webp"
}
```

Окончательные коды ошибок: `UNSUPPORTED_FORMAT`, `FILE_TOO_LARGE`,
`INVALID_IMAGE`, `UNSAFE_INPUT`. Временные: `SOURCE_UNAVAILABLE`,
`STORAGE_UNAVAILABLE`. Повтор команды должен вернуть те же объекты или безопасно
перезаписать их.
