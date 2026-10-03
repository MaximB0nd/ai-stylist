# Договор службы определения цветотипа

## Endpoint

```text
POST /v1/classify
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

`image` должен быть нормализованным RGB sRGB PNG с белым фоном. Нарушение
формата возвращает `422 INPUT_UNPROCESSABLE`, а не результат классификации.

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

## Недостаточно надёжный результат

HTTP `200`:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "REJECTED",
  "reasons": ["COLOR_TYPE_UNCERTAIN"],
  "model_version": "jiwoonkim00/personal-color-classifier@revision"
}
```

## Инварианты

- Успех содержит `color_type` и не содержит `decision`, `reasons` или confidence.
- `REJECTED` содержит единственную причину `COLOR_TYPE_UNCERTAIN` и не содержит
  `color_type`.
- Confidence, logits, вероятности классов и внутренний порог не возвращаются.
- Системные ошибки используют HTTP-коды и форму ошибки общего договора.
