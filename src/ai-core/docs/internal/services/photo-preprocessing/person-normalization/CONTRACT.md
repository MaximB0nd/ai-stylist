# Договор службы нормализации человека

## Endpoint

```text
POST /v1/normalize
Content-Type: application/json
```

Запрос использует авторизацию и правила файлов из
[общего договора](../../CONTRACT.md).

## Запрос

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "image": {
    "read_url": "https://temporary-files.example/opaque-read-token",
    "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "output": {
    "write_url": "https://temporary-files.example/opaque-write-token",
    "width": 512,
    "height": 512
  }
}
```

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

Допустимые коды ошибки `422`:

| Код | Значение |
| --- | --- |
| `PERSON_NOT_FOUND` | человек не найден |
| `MULTIPLE_PEOPLE` | нельзя однозначно выбрать одного человека |
| `PERSON_MASK_UNAVAILABLE` | модель не построила пригодную маску человека |

При ошибке служба не публикует частичный результат. Сбой выполнения модели
возвращает `500 INFERENCE_FAILED`, а ошибка записи по `write_url` — подходящий
`502`, `504` или `409` из общего договора.

## Инварианты

- Только HTTP `200` содержит `artifact`; без артефакта успешного ответа нет.
- Ошибка `422` содержит `model_version`, использованную при анализе входа.
- `artifact.width` и `artifact.height` равны запрошенным значениям.
- `artifact.checksum_sha256` вычисляется по записанным байтам PNG.
- Ответ не содержит исходную или промежуточную маску.
- Остальные ошибки используют HTTP-коды и Problem Details из общего договора.
