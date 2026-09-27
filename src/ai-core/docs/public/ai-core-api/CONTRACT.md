# Договор внешнего интерфейса AI Core

Этот файл — единственный источник истины для взаимодействия основного сервера с
AI Core.

## Общие правила

- Все операции выполняются во внутренней сети по HTTPS.
- Тело и ответ имеют `Content-Type: application/json`.
- Основной сервер передаёт `Authorization: Bearer <service-token>`.
- Создание задания требует непрозрачный заголовок `Idempotency-Key`.
- Повтор создания с тем же ключом возвращает то же задание.
- Тот же ключ с другим телом возвращает `409 IDEMPOTENCY_CONFLICT`.
- Тела запросов не содержат идентификатор пользователя.
- Количество результатов задаётся `requested_image_count`; успешное задание всегда
  содержит ровно это количество результатов.

## Возможности службы

```text
GET /v1/capabilities
```

```json
{
  "api_version": "1",
  "min_image_count": 1,
  "max_image_count": 10,
  "min_input_url_ttl_seconds": 1200,
  "result_download_ttl_seconds": 86400
}
```

Ответ вычисляется из текущих значений
[единого реестра настроек](../../internal/configuration.md): минимальный срок входных
ссылок равен бюджету ожидания подготовки плюс срок команды воркеру. Основной
сервер проверяет ответ при запуске и не копирует эти числа в свой договор.

## Создание задания

```text
POST /v1/jobs
Idempotency-Key: <непрозрачный уникальный ключ>
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

AI Core проверяет диапазон количества и остаточный срок входных ссылок. Значения
ограничений берутся из `GET /v1/capabilities`, но не являются полями запроса.

`age` — целое число от 18 до 100, `height_cm` — целое число от 120 до 230,
`gender` — `female`, `male` или `unspecified`. Списки предпочтений не содержат
повторов и имеют не более 20 элементов; `description` содержит не более 1000
знаков. Неизвестное поле отклоняется как `INVALID_REQUEST`.

### Допустимые предпочтения

- `occasion`: `casual`, `study`, `office`, `evening`, `sport` или `travel`;
- каждый элемент `styles`: `classic`, `minimalism`, `romantic`, `streetwear` или
  `sport`;
- каждый элемент `shoes`: `loafers`, `sneakers`, `boots`, `heels` или `any`;
- каждый элемент `impressions`: `confident`, `elegant`, `relaxed`, `bright` или
  `professional`.

Этот раздел — единственный справочник значений внешнего запроса.

## Передача файлов

AI Core самостоятельно хранит входные копии, промежуточные файлы и готовые
результаты во временном хранилище. Основной сервер не передаёт AI Core ключи
своего постоянного хранилища.

Байты изображений не передаются через этот интерфейс. После завершения основной
сервер получает для каждого результата короткую ссылку, скачивает файл напрямую,
проверяет SHA-256 и сохраняет файл у себя. Внутреннее устройство временного
хранилища не является частью внешнего договора.

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

Допустимые состояния:

- `QUEUED`;
- `PROCESSING`;
- `COMPLETED`;
- `FAILED`;
- `CANCELLED`.

`COMPLETED`, `FAILED` и `CANCELLED` являются конечными.

## Завершённое задание

```json
{
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "COMPLETED",
  "requested_image_count": 2,
  "accepted_image_count": 2,
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
    },
    {
      "order_index": 1,
      "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9M9",
      "download_url": "https://files.example/temporary-result-1",
      "download_url_expires_at": "2026-09-27T12:00:00Z",
      "checksum_sha256": "sha256:example-1",
      "size_bytes": 1126400,
      "format": "webp",
      "width": 1024,
      "height": 1536,
      "model_version": "image-model@example",
      "prompt_version": "photographer-v1",
      "outfit_spec_version": "1.0",
      "seed": 67890
    }
  ],
  "error": null
}
```

Частичный успех наружу не выдаётся. Если получить полное количество результатов
не удалось, задание переходит в `FAILED`. `COMPLETED` означает, что полный набор
временных результатов готов к скачиванию; постоянное хранение находится вне
AI Core. До `results_available_until` повторный `GET` может обновлять истекающие
`download_url` через внутреннюю службу временных файлов, не меняя `artifact_id`.

## Подтверждение получения результатов

После проверки контрольных сумм и сохранения всех результатов основной сервер
подтверждает получение:

```text
POST /v1/jobs/{job_id}/results/ack
```

Успешный ответ — `204 No Content`. Операция доступна только для `COMPLETED`,
идемпотентна и не меняет конечное состояние. AI Core не получает сведения о том,
куда основной сервер сохранил файлы. Если подтверждение не пришло до
`results_available_until`, AI Core запускает очистку временных результатов, а
последующий запрос файлов возвращает `410 RESULT_EXPIRED`.

Основной сервер отвечает за защиту от повторного сохранения одного
`artifact_id`. AI Core отвечает за то, что повторный запрос состояния возвращает
тот же `artifact_id` и те же метаданные файла.

## Отмена

```text
POST /v1/jobs/{job_id}/cancel
```

Отмена идемпотентна. После `CANCELLED` поздний внутренний результат не может
вернуть задание в работу.

## Уведомление о состоянии

AI Core отправляет уведомления только на доверенный адрес из настроек окружения.
Запрос содержит `X-AI-Core-Timestamp` в виде целого числа секунд Unix и
`X-AI-Core-Signature` в виде шестнадцатеричной строки. Подписываемые байты:
`timestamp + "." + raw_body`, кодировка UTF-8. Подпись — HMAC-SHA256 с общим
секретом. Получатель сравнивает подпись без утечки времени, отклоняет событие
старше пяти минут и второй раз не применяет тот же `event_id`.

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

- `event_id` устраняет повторную обработку;
- `sequence` не позволяет применить старое состояние поверх нового;
- любой `2xx` подтверждает доставку;
- текущее состояние всегда можно уточнить через `GET /v1/jobs/{job_id}`.
- уведомление не содержит файлы; после `COMPLETED` основной сервер получает их
  через `GET` и подтверждает операцией `results/ack`.

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

Клиент получает безопасный код без внутренних трассировок и чувствительных данных.

| HTTP-код | Код ошибки | Значение |
| ---: | --- | --- |
| `400` | `INVALID_REQUEST` | Неверный JSON или поля |
| `401` | `UNAUTHORIZED` | Нет действительного токена |
| `404` | `JOB_NOT_FOUND` | Задание не найдено |
| `409` | `IDEMPOTENCY_CONFLICT` | Ключ повторён с другим телом |
| `409` | `INVALID_JOB_STATE` | Операция невозможна в текущем состоянии |
| `410` | `RESULT_EXPIRED` | Срок получения временных результатов истёк |
| `422` | `UNSUPPORTED_INPUT` | Файл или значение не поддерживается |
| `429` | `TOO_MANY_REQUESTS` | Временно превышена допустимая нагрузка |
| `503` | `SERVICE_UNAVAILABLE` | Служба временно не готова |

Для `429` и `503` ответ содержит `Retry-After`. Повтор безопасен с тем же ключом
идемпотентности. Для `FAILED` поле `error` заполнено тем же безопасным объектом;
для `CANCELLED` оно равно `null`.
