# Договор службы проверки личности

## Endpoint

```text
POST /v1/compare
Content-Type: application/json
```

Запрос использует правила файлов из
[общего договора](../../CONTRACT.md).

## Запрос

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "face_image": {
    "read_url": "http://temporary-files.example/artifacts/01J8Z8Y7W6V5T4S3R2Q1P0N9B1/read",
    "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "body_image": {
    "read_url": "http://temporary-files.example/artifacts/01J8Z8Y7W6V5T4S3R2Q1P0N9B2/read",
    "checksum_sha256": "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
  }
}
```

Имена полей описывают роль изображения в сравнении и не требуют конкретного
происхождения файла.

## Результат сравнения

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "SAME_PERSON",
  "model_versions": {
    "face_detector": "opencv/face_detection_yunet@revision",
    "face_recognizer": "opencv/face_recognition_sface@revision"
  }
}
```

`decision` равен `SAME_PERSON` или `DIFFERENT_PERSON`. Оба значения являются
завершённым результатом сравнения, а не ошибкой.

## Сравнение невозможно из-за входа

HTTP `422`, `Content-Type: application/problem+json`:

```json
{
  "type": "urn:ai-core:problem:body-image-face-not-found",
  "title": "A comparable face was not found",
  "status": 422,
  "detail": "The body image does not contain a usable face.",
  "instance": "urn:uuid:4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "code": "BODY_IMAGE_FACE_NOT_FOUND",
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "retryable": false,
  "model_versions": {
    "face_detector": "opencv/face_detection_yunet@revision",
    "face_recognizer": "opencv/face_recognition_sface@revision"
  }
}
```

Допустимые коды ошибки `422`:

| Код | Значение |
| --- | --- |
| `FACE_IMAGE_FACE_NOT_FOUND` | в `face_image` лицо не найдено |
| `FACE_IMAGE_MULTIPLE_FACES` | в `face_image` найдено больше одного лица |
| `FACE_IMAGE_FACE_TOO_SMALL` | лицо в `face_image` недостаточно крупное |
| `FACE_IMAGE_FACE_UNUSABLE` | лицо в `face_image` нельзя корректно выровнять |
| `BODY_IMAGE_FACE_NOT_FOUND` | в `body_image` лицо не найдено |
| `BODY_IMAGE_MULTIPLE_FACES` | в `body_image` найдено больше одного лица |
| `BODY_IMAGE_FACE_TOO_SMALL` | лицо в `body_image` недостаточно крупное |
| `BODY_IMAGE_FACE_UNUSABLE` | лицо в `body_image` нельзя корректно выровнять |

Служба сначала применяет YuNet к каждому исходному изображению, отклоняет
неподходящее количество или размер лиц и выравнивает единственное лицо по пяти
landmarks. Только после этого SFace строит и сравнивает embeddings. Порядок и
версии этапов являются частью model bundle и не задаются вызывающей стороной.

## Инварианты

- Успешный `decision` принимает только `SAME_PERSON` или `DIFFERENT_PERSON`.
- HTTP `200` означает, что сравнение выполнено и содержит `decision`.
- Если сравнение невозможно, служба возвращает `422`, а не `REJECTED`.
- Успех и предметная ошибка `422` содержат обе записи `model_versions`.
- Similarity score, embedding и применённый порог не возвращаются.
- Остальные ошибки используют HTTP-коды и Problem Details из общего договора.
