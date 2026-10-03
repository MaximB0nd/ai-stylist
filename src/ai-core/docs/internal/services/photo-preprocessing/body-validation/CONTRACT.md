# Договор службы проверки полного роста

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

`image` — исходная фотография человека в полный рост. Один вызов принимает
ровно один файл.

## Принятое изображение

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "ACCEPTED",
  "reasons": [],
  "model_versions": {
    "person_detection": "opencv/person_detection_mediapipe@revision",
    "pose_estimation": "opencv/pose_estimation_mediapipe@revision"
  }
}
```

## Отклонённое изображение

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "REJECTED",
  "reasons": ["BODY_CROPPED"],
  "model_versions": {
    "person_detection": "opencv/person_detection_mediapipe@revision",
    "pose_estimation": "opencv/pose_estimation_mediapipe@revision"
  }
}
```

Допустимые причины:

| Код | Значение |
| --- | --- |
| `PERSON_NOT_FOUND` | человек не найден |
| `MULTIPLE_PEOPLE` | найдено больше одного человека |
| `BODY_CROPPED` | критическая часть тела находится за границей кадра |
| `BODY_OCCLUDED` | критическая часть тела перекрыта |
| `IMAGE_TOO_SMALL` | разрешения недостаточно для следующих этапов |
| `IMAGE_TOO_BLURRY` | резкости недостаточно для следующих этапов |

`PERSON_NOT_FOUND` и `MULTIPLE_PEOPLE` не объединяются с причинами качества
конкретного человека. Координаты, поза и измеренные значения не возвращаются.

## Инварианты

- `decision` принимает только `ACCEPTED` или `REJECTED`.
- Для `ACCEPTED` массив `reasons` пуст.
- Для `REJECTED` массив `reasons` непустой.
- Оба поля `model_versions` обязательны, поскольку модели образуют один bundle.
- `REJECTED` является результатом успешно выполненной проверки, поэтому имеет
  HTTP `200`; невозможность прочитать или обработать файл является ошибкой.
- Ошибки используют HTTP-коды и Problem Details из общего договора.
