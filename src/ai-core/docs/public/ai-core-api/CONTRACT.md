# Договор внешнего интерфейса AI Core

## Транспорт

| Правило | Значение |
| --- | --- |
| Сеть | внутренняя, HTTPS |
| Формат | `application/json` |
| Авторизация | `Authorization: Bearer <service-token>` |
| Идентификатор пользователя | не передаётся |
| Количество результатов | `requested_image_count` |
| Частичный успех | запрещён |

## Возможности

```text
GET /v1/capabilities
```

Ответ содержит версию интерфейса, допустимое количество изображений и требования
к сроку действия ссылок. Конкретные значения фиксируются при реализации внешнего интерфейса.

## Создание задания

```text
POST /v1/jobs
Idempotency-Key: <уникальный ключ>
```

```json
{
  "requested_image_count": 7,
  "inputs": {
    "face_photo_url": "https://files.example/temporary-face",
    "body_photo_url": "https://files.example/temporary-body",
    "expires_at": "2026-09-27T12:00:00Z"
  },
  "person": {
    "age": 26,
    "height_cm": 172,
    "gender": "female"
  },
  "preferences": {
    "occasion": "office",
    "styles": ["classic", "minimalism"],
    "shoes": ["loafers"],
    "impressions": ["confident", "elegant"],
    "description": "Сдержанные образы для офиса"
  }
}
```

```json
{
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "QUEUED",
  "requested_image_count": 7,
  "status_url": "/v1/jobs/c84dfb50-f331-4c12-88f5-3c1a3e6015aa"
}
```

### Проверка запроса

| Поле | Ограничение |
| --- | --- |
| `requested_image_count` | диапазон из `/v1/capabilities` |
| `inputs.expires_at` | остаток не меньше `min_input_url_ttl_seconds` |
| `age` | целое, `18..100` |
| `height_cm` | целое, `120..230` |
| `gender` | `female`, `male`, `unspecified` |
| списки предпочтений | без повторов, до 20 элементов |
| `description` | до 1000 знаков |
| неизвестное поле | `INVALID_REQUEST` |

### Повтор запроса

1. Проверить и привести тело.
2. Вычислить SHA-256 тела.
3. Тот же ключ и тело: вернуть прежнее задание.
4. Тот же ключ и другое тело: `409 IDEMPOTENCY_CONFLICT`.

### Допустимые предпочтения

| Поле | Значения |
| --- | --- |
| `occasion` | `casual`, `study`, `office`, `evening`, `sport`, `travel` |
| `styles[]` | `classic`, `minimalism`, `romantic`, `streetwear`, `sport` |
| `shoes[]` | `loafers`, `sneakers`, `boots`, `heels`, `any` |
| `impressions[]` | `confident`, `elegant`, `relaxed`, `bright`, `professional` |

## Получение состояния

```text
GET /v1/jobs/{job_id}
```

```json
{
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "PROCESSING",
  "requested_image_count": 7,
  "accepted_image_count": 3,
  "failed_attempt_count": 1,
  "updated_at": "2026-09-27T10:30:00Z",
  "error": null
}
```

Состояния: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED`.

Конечные: `COMPLETED`, `FAILED`, `CANCELLED`.

## Завершённое задание

```json
{
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "COMPLETED",
  "requested_image_count": 1,
  "accepted_image_count": 1,
  "result_delivery_status": "AVAILABLE",
  "results_available_until": "2026-09-28T10:00:00Z",
  "results": [
    {
      "order_index": 0,
      "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9M8",
      "download_url": "https://files.example/temporary-result-0",
      "download_url_expires_at": "2026-09-27T12:00:00Z",
      "checksum_sha256": "sha256:example-0",
      "size_bytes": 1048576,
      "format": "webp",
      "width": 1024,
      "height": 1536,
      "model_version": "image-model@example",
      "prompt_version": "photographer-v1",
      "outfit_spec_version": "1.0",
      "seed": 12345
    }
  ],
  "error": null
}
```

| `result_delivery_status` | `results` | Значение |
| --- | --- | --- |
| `AVAILABLE` | метаданные и ссылки | можно скачать |
| `ACKNOWLEDGED` | `[]` | основной сервер подтвердил сохранение |
| `EXPIRED` | `[]` | срок истёк до ACK |

- `COMPLETED` содержит ровно `requested_image_count` результатов.
- Повторный `GET` при `AVAILABLE` может обновить ссылки без смены `artifact_id`.
- После `ACKNOWLEDGED` или `EXPIRED` состояние остаётся `COMPLETED`.
- Постоянное хранение находится вне AI Core.

## Подтверждение получения результатов

```text
POST /v1/jobs/{job_id}/results/ack
```

| Условие | Ответ | Новое состояние доставки |
| --- | --- | --- |
| `AVAILABLE` до срока | `204` | `ACKNOWLEDGED` |
| повтор после ACK | `204` | `ACKNOWLEDGED` |
| после срока | `409 RESULTS_EXPIRED` | `EXPIRED` |

Смена `AVAILABLE` на `ACKNOWLEDGED` или `EXPIRED` атомарна. Первая запись побеждает.

## Передача файлов

1. Основной сервер скачивает `download_url` через службу временных файлов.
2. Проверяет `checksum_sha256`.
3. Сохраняет файл постоянно.
4. Защищается от повтора по `artifact_id`.
5. Отправляет ACK.

Байты не проходят через внешний интерфейс и главный оркестратор AI Core.

## Отмена

```text
POST /v1/jobs/{job_id}/cancel
```

- Идемпотентна.
- Конечное состояние: `CANCELLED`.
- Поздний внутренний результат не меняет состояние.

## Уведомление о состоянии

Заголовки:

```text
X-AI-Core-Timestamp: <Unix seconds>
X-AI-Core-Signature: <hex HMAC-SHA256>
```

Подписываемые байты: `timestamp + "." + raw_body`, UTF-8.

```json
{
  "event_id": "4964143c-b10a-4d89-80b5-5cf9d488d8e2",
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "sequence": 5,
  "status": "PROCESSING",
  "progress": {
    "requested_image_count": 7,
    "accepted_image_count": 3
  },
  "occurred_at": "2026-09-27T10:30:00Z",
  "error": null
}
```

| Поле | Правило |
| --- | --- |
| `event_id` | идемпотентность события |
| `sequence` | запрет применения старого состояния |
| время подписи | отклонить старше 5 минут |
| успешная доставка | любой `2xx` |

Адрес и секрет берутся из настроек. Уведомление не содержит файлов.

## Ошибка

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Запрос не прошёл проверку",
    "retryable": false
  }
}
```

| HTTP | Код | Условие |
| ---: | --- | --- |
| `400` | `INVALID_REQUEST` | неверные поля или JSON |
| `401` | `UNAUTHORIZED` | неверный токен |
| `404` | `JOB_NOT_FOUND` | нет задания |
| `409` | `IDEMPOTENCY_CONFLICT` | ключ использован с другим телом |
| `409` | `INVALID_JOB_STATE` | операция запрещена состоянием |
| `409` | `RESULTS_EXPIRED` | ACK после срока |
| `422` | `UNSUPPORTED_INPUT` | файл или значение не поддерживается |
| `429` | `TOO_MANY_REQUESTS` | превышен предел нагрузки |
| `503` | `SERVICE_UNAVAILABLE` | служба не готова |

`429` и `503` содержат `Retry-After`.
