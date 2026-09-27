# Сообщения RabbitMQ

## Очереди

| Воркер | Команды | Результаты |
| --- | --- | --- |
| Подготовка | `ai.photo.prepare.commands` | `ai.photo.prepare.results` |
| Стилист | `ai.outfit.style.commands` | `ai.outfit.style.results` |
| Генерация | `ai.image.generate.commands` | `ai.image.generate.results` |
| Проверка | `ai.image.verify.commands` | `ai.image.verify.results` |
| Уведомления | `ai.status.notify.commands` | `ai.status.notify.results` |

У каждой очереди команд есть отдельная очередь окончательных ошибок.

## Оболочка

```json
{
  "message_id": "67b6fd73-9699-4e50-8cc0-7fd1865ed46a",
  "message_type": "worker.image.generate.command",
  "schema_version": "1.0",
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "worker_run_id": "c9f5ad1d-b484-457f-829b-fd90d6f58ac8",
  "result_index": 3,
  "attempt": 2,
  "lease_token": 17,
  "lease_expires_at": "2026-09-27T10:25:00Z",
  "correlation_id": "56912f8e-846e-409a-b894-d7f7b5834607",
  "created_at": "2026-09-27T10:00:00Z",
  "payload": {}
}
```

| Поле | Назначение |
| --- | --- |
| `message_id` | Идемпотентность сообщения |
| `message_type` | Тип команды или результата |
| `schema_version` | Версия оболочки и `payload` |
| `job_id` | Задание |
| `worker_run_id` | Запуск воркера |
| `result_index` | Номер изображения `0..N-1`; отсутствует для подготовки и уведомлений |
| `attempt` | Номер попытки |
| `lease_token` | Защита от устаревшего результата |
| `lease_expires_at` | Конец аренды |
| `correlation_id` | Связь команды и результата |
| `created_at` | UTC |
| `payload` | Договор конкретного воркера |

## Результат воркера

Успех:

```json
{"status": "SUCCEEDED"}
```

Ошибка:

```json
{
  "status": "FAILED",
  "error": {
    "code": "MODEL_UNAVAILABLE",
    "message": "Модель временно недоступна",
    "retryable": true,
    "retry_after_seconds": 30
  }
}
```

Отмена:

```json
{"status": "CANCELLED"}
```

| Поле | Правило |
| --- | --- |
| `code` | Определяет договор воркера |
| `message` | Без трассировки и секретов |
| `retryable` | Разрешение новой технической попытки |
| `retry_after_seconds` | Только для временной ошибки; необязательно |

Повтор создаёт только главный оркестратор. `CANCELLED` не повторяется автоматически.

## Доставка

- Постоянные очереди и сообщения.
- Подтверждение публикации RabbitMQ.
- Доставка минимум один раз.
- Оркестратор сохраняет результат до подтверждения сообщения.
- Воркер публикует результат до подтверждения команды.
- Повторная доставка сохраняет `message_id`, `worker_run_id`, `lease_token`, `attempt`.
- Новая попытка получает новые идентификаторы.
- Повторный `message_id` не применяется.
- Запись файла и уведомление идемпотентны.
- Неверная схема отправляется в очередь окончательных ошибок.

## Версии

- Новое необязательное поле: совместимо.
- Удаление поля, новый тип или новый смысл: новая старшая версия.
- Во время обновления поддерживаются текущая и предыдущая версии.
