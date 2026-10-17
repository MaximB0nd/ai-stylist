# Договор службы проверки лица

## Endpoint

```text
POST /v1/validate
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

`image` — исходная фотография лица. Один вызов принимает ровно один файл.

## Принятое изображение

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "ACCEPTED",
  "reasons": [],
  "model_version": "opencv/face_detection_yunet@revision"
}
```

## Отклонённое изображение

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "REJECTED",
  "reasons": ["FACE_TOO_BLURRY"],
  "model_version": "opencv/face_detection_yunet@revision"
}
```

Допустимые причины:

| Код | Значение |
| --- | --- |
| `FACE_NOT_FOUND` | лицо не найдено |
| `MULTIPLE_FACES` | найдено больше одного лица |
| `FACE_TOO_SMALL` | лицо занимает недостаточную часть изображения |
| `FACE_TOO_BLURRY` | резкости недостаточно для следующих этапов |
| `INVALID_FACE_POSE` | поворот или наклон выходит за допустимый диапазон |
| `INVALID_EXPOSURE` | лицо критически недоэкспонировано или переэкспонировано |
| `UNEVEN_LIGHTING` | освещение лица недостаточно равномерно для цветотипа |

`FACE_NOT_FOUND` и `MULTIPLE_FACES` не объединяются с причинами качества
конкретного лица. Пороги и измеренные значения наружу не возвращаются.

## Инварианты

- `decision` принимает только `ACCEPTED` или `REJECTED`.
- Для `ACCEPTED` массив `reasons` пуст.
- Для `REJECTED` массив `reasons` непустой.
- `REJECTED` является результатом успешно выполненной проверки, поэтому имеет
  HTTP `200`; невозможность прочитать или обработать файл является ошибкой.
- Ошибки используют HTTP-коды и Problem Details из общего договора.
