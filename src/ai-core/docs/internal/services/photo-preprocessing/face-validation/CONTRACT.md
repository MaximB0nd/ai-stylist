# Договор службы проверки лица

## Endpoint

```text
POST /v1/validate
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
- Системные ошибки используют HTTP-коды и форму ошибки общего договора.
