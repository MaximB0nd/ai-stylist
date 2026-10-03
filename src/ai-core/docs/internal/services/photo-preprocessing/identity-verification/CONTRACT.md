# Договор службы проверки личности

## Endpoint

```text
POST /v1/compare
Content-Type: application/json
```

Запрос использует авторизацию и правила файлов из
[общего договора](../../CONTRACT.md).

## Запрос

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "face_image": {
    "read_url": "https://temporary-files.example/face-read-token",
    "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "body_image": {
    "read_url": "https://temporary-files.example/body-read-token",
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
  "reasons": [],
  "model_version": "opencv/face_recognition_sface@revision"
}
```

`decision` равен `SAME_PERSON` или `DIFFERENT_PERSON`. Оба значения являются
завершённым результатом сравнения, а не ошибкой.

## Сравнение невозможно

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "REJECTED",
  "reasons": ["BODY_IMAGE_FACE_NOT_FOUND"],
  "model_version": "opencv/face_recognition_sface@revision"
}
```

Допустимые причины:

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

## Инварианты

- `decision` принимает только `SAME_PERSON`, `DIFFERENT_PERSON` или `REJECTED`.
- Для результата сравнения массив `reasons` пуст.
- Для `REJECTED` массив `reasons` непустой.
- Similarity score, embedding и применённый порог не возвращаются.
- Системные ошибки используют HTTP-коды и форму ошибки общего договора.
