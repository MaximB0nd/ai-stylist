# Договор службы нормализации человека

## Endpoint

```text
POST /v1/normalize
Content-Type: application/json
```

Запрос использует правила файлов из
[общего договора](../../CONTRACT.md).

## Запрос

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "profile": "face",
  "image": {
    "read_url": "http://artifact-service/internal/v1/artifacts/01J8Z8Y7W6V5T4S3R2Q1P0N9B1/content",
    "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "output": {
    "write_url": "http://artifact-service/internal/v1/artifacts/01J8Z8Y7W6V5T4S3R2Q1P0N9B3/content",
    "width": 512,
    "height": 512
  }
}
```

`profile` принимает `face` или `full_body` и явно сообщает правила компоновки;
служба не определяет назначение фотографии по содержимому или размерам.
Изображение должно быть ранее принято соответствующей проверкой пригодности и
содержать одного человека. Результат проверки не передаётся и normalizer не
знает, какой сервис или клиент обеспечил это предусловие.

`width` и `height` — целые числа от `1` до `2048`; это начальный безопасный
предел для CPU-развёртывания. Превышение возвращает `422 VALIDATION_ERROR`. Служба
сохраняет пропорции человека, центрирует его и заполняет свободную область
цветом `#FFFFFF`. Формат результата всегда RGB sRGB PNG; формат, фон и алгоритм
`contain` не являются параметрами запроса.

## Нормализованное изображение

HTTP `200` возвращается только после успешной записи результата:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "artifact": {
    "checksum_sha256": "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    "media_type": "image/png",
    "width": 512,
    "height": 512,
    "size_bytes": 245760
  },
  "model_version": "opencv/human_segmentation_pphumanseg@revision"
}
```

## Нормализация невозможна из-за входа

HTTP `422`, `Content-Type: application/problem+json`:

```json
{
  "type": "urn:ai-core:problem:person-mask-unavailable",
  "title": "The person cannot be normalized",
  "status": 422,
  "detail": "A usable person mask could not be produced from the image.",
  "instance": "urn:uuid:4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "code": "PERSON_MASK_UNAVAILABLE",
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "retryable": false,
  "model_version": "opencv/human_segmentation_pphumanseg@revision"
}
```

`PERSON_MASK_UNAVAILABLE` означает, что PPHumanSeg не построил маску, которая
удовлетворяет геометрическим ограничениям выбранного `profile`. Служба не
возвращает `PERSON_NOT_FOUND` или `MULTIPLE_PEOPLE`: количество людей относится
к входному предусловию и проверяется до normalizer.

При ошибке служба не публикует частичный результат. Сбой выполнения модели
возвращает `500 INFERENCE_FAILED`, а ошибка записи по `write_url` — подходящий
`502`, `504` или `409` из общего договора.

## Инварианты

- Только HTTP `200` содержит `artifact`; без артефакта успешного ответа нет.
- Ошибка `422` содержит `model_version`, использованную при анализе входа.
- `artifact.width` и `artifact.height` равны запрошенным значениям.
- `artifact.checksum_sha256` вычисляется по записанным байтам PNG.
- Ответ не содержит исходную или промежуточную маску.
- Служба не обещает исправить нарушение предусловия о количестве людей.
- Остальные ошибки используют HTTP-коды и Problem Details из общего договора.
