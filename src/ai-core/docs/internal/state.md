# Состояние AI Core

## Владельцы

| Состояние | Владелец |
| --- | --- |
| Задание, этап, попытка, результат | Главный оркестратор |
| Резерв `OutfitSpec` | Главный оркестратор |
| `inbox`, `outbox`, события | Главный оркестратор |
| Веса модели и кэш процесса | Воркер |

- Одна PostgreSQL главного оркестратора.
- Воркеры без доступа к PostgreSQL.
- Внешний интерфейс использует [договор оркестратора](services/main-orchestrator/CONTRACT.md).

## Таблицы

### `ai_jobs`

| Поле | Значение |
| --- | --- |
| `job_id` | Идентификатор AI Core |
| `idempotency_key_hash` | SHA-256 ключа повтора; `UNIQUE` |
| `request_hash` | SHA-256 приведённого запроса |
| `request_payload` | Полный приведённый запрос |
| `contract_version` | Версия внешнего договора |
| `outfit_schema_version` | Версия `OutfitSpec` |
| `status` | `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `result_delivery_status` | `AVAILABLE`, `ACKNOWLEDGED`, `EXPIRED` |
| `requested_image_count` | Запрошено |
| `accepted_image_count` | Принято |
| `error` | Безопасная ошибка |
| `cancelled_at` | Время отмены |
| `results_available_until` | Срок результатов |
| `results_acknowledged_at` | Время ACK |
| `created_at`, `updated_at` | UTC |

### Остальные таблицы

| Таблица | Данные | Ограничение |
| --- | --- | --- |
| `ai_job_images` | номер, состояние, комплект, попытки, параметры модели, `artifact_id`, ошибка | один номер на задание |
| `ai_worker_runs` | `worker_run_id`, тип, место, попытка, состояние, аренда, версия, итог | `worker_run_id` уникален |
| `ai_outfits` | `job_id`, нормализованный хеш, состояние резерва | `UNIQUE(job_id, normalized_hash)` |
| `ai_status_events` | `event_id`, `job_id`, `sequence`, состояние, время | неизменяемые записи |
| `ai_artifacts` | файл, назначение, место, ключ объекта, SHA-256, размер, формат, сроки, состояния | `UNIQUE(job_id, worker_run_id, purpose, slot)` |
| `inbox` | применённые `message_id` | `message_id` уникален |
| `outbox` | непереданные команды и события | одна транзакция с изменением задания |

Ссылки на файлы в базе не хранятся. Жизненный цикл: [artifacts.md](artifacts.md).

## Создание задания

1. Проверить и привести запрос.
2. Вычислить `idempotency_key_hash` и `request_hash`.
3. Одной транзакцией:
   - новый ключ → создать задание;
   - тот же ключ и тот же запрос → вернуть задание;
   - тот же ключ и другой запрос → `IDEMPOTENCY_CONFLICT`.
4. Сохранить `request_payload` до первой команды.

`request_payload` доступен до завершения задания. Защита: [data-policy.md](data-policy.md).

## Аренда

- Оркестратор создаёт `worker_run_id`, `lease_token`, `lease_expires_at`.
- Срок: [configuration.md](configuration.md#главный-оркестратор).
- Принимается только текущий `lease_token` до `lease_expires_at`.
- Поздний результат не меняет задание.
- Новая попытка получает новые идентификаторы.
- Первая версия не продлевает аренду.

## Восстановление

1. Опубликовать записи `outbox`.
2. Найти истёкшие аренды.
3. Создать попытки только для незавершённой работы.
4. Не применять известные `message_id`.
5. Не повторять принятые результаты.

## Отмена

- Прекратить новые команды.
- Пометить активные запуски отменёнными.
- Не принимать поздние результаты.
- Запустить очистку временных файлов.
