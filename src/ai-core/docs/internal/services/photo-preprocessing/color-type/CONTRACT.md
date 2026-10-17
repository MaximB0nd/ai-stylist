# Договор службы определения цветотипа

## Endpoint

```text
POST /v1/classify
Content-Type: application/json
```

Запрос использует правила файлов из
[общего договора](../../CONTRACT.md).

## Запрос

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "image": {
    "read_url": "http://artifact-service/internal/v1/artifacts/01J8Z8Y7W6V5T4S3R2Q1P0N9B1/content",
    "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }
}
```

`image` должен быть нормализованным RGB sRGB PNG с белым фоном. Другой файловый
формат возвращает `422 UNSUPPORTED_IMAGE_TYPE`; PNG, нарушающий требования
нормализации, возвращает `422 INVALID_NORMALIZED_IMAGE`.

Модель и её детерминированные tensor transforms образуют одну версионируемую
inference-конфигурацию. Служба может читать, декодировать, resize, crop и
нормализовать tensor в памяти, но не изменяет и не перезаписывает входной
артефакт. Production-конфигурация не должна зависеть от отдельной detector или
skin-segmentation модели: классификатор выбирается или дообучается на точном
выходе normalizer.

## Определённый цветотип

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "color_type": "summer",
  "model_version": "jiwoonkim00/personal-color-classifier@revision"
}
```

`color_type` принимает только `spring`, `summer`, `autumn` или `winter`.
Такой ответ допустим только для модели и порога, прошедших закрытый benchmark на
целевом pipeline. Публичные метрики исходного репозитория модели не заменяют эту
проверку.

## Цветотип нельзя определить надёжно

HTTP `422`, `Content-Type: application/problem+json`:

```json
{
  "type": "urn:ai-core:problem:color-type-uncertain",
  "title": "The color type cannot be determined reliably",
  "status": 422,
  "detail": "The image does not produce a result above the accepted threshold.",
  "instance": "urn:uuid:4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "code": "COLOR_TYPE_UNCERTAIN",
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "retryable": false,
  "model_version": "jiwoonkim00/personal-color-classifier@revision"
}
```

Дополнительные коды ошибки `422`:

| Код | Значение |
| --- | --- |
| `INVALID_NORMALIZED_IMAGE` | PNG не соответствует входному договору службы |
| `COLOR_TYPE_UNCERTAIN` | модель не может вернуть надёжный цветотип |

## Инварианты

- Только HTTP `200` содержит `color_type`.
- Ошибка `COLOR_TYPE_UNCERTAIN` содержит `model_version`, но не содержит
  `color_type` или confidence.
- Confidence, logits, вероятности классов и внутренний порог не возвращаются.
- `model_version` однозначно определяет веса, tensor transforms и порог отказа.
- Остальные ошибки используют HTTP-коды и Problem Details из общего договора.
