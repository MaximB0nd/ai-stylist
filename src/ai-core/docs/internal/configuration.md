# Настройки

Секреты не хранятся в Git и журналах. В Git допустим только `.env.example` без значений.

## Общие

| Переменная | Значение | Назначение |
| --- | ---: | --- |
| `AI_CORE_SERVICE_NAME` | обязательно | Имя службы |
| `AI_CORE_ENVIRONMENT` | `local` | Окружение |
| `AI_CORE_LOG_LEVEL` | `INFO` | Уровень журнала |
| `AI_CORE_RABBITMQ_URL` | обязательно | RabbitMQ |
| `AI_CORE_RABBITMQ_PREFETCH` | `1` | Команды на копию воркера |
| `AI_CORE_ENVELOPE_SCHEMA_VERSION` | `1.0` | Версия оболочки сообщения |

## Внешний интерфейс

| Переменная | Значение | Назначение |
| --- | ---: | --- |
| `AI_CORE_INTERNAL_TOKEN` | секрет | Токен основного сервера |
| `AI_CORE_ORCHESTRATOR_URL` | обязательно | Главный оркестратор |
| `AI_CORE_REQUEST_TIMEOUT_SECONDS` | `10` | Внутренний HTTP-запрос |
| `AI_CORE_MIN_IMAGE_COUNT` | `1` | Минимум результатов |
| `AI_CORE_MAX_IMAGE_COUNT` | `10` | Максимум результатов |

## Главный оркестратор

| Переменная | Значение | Назначение |
| --- | ---: | --- |
| `AI_CORE_DATABASE_URL` | обязательно | PostgreSQL |
| `AI_CORE_OUTBOX_INTERVAL_MS` | `250` | Публикация `outbox` |
| `AI_CORE_WORKER_QUEUE_BUDGET_SECONDS` | `600` | Ожидание в очереди |
| `AI_CORE_WORKER_ATTEMPT_TIMEOUT_SECONDS` | `900` | Выполнение после получения |
| `AI_CORE_JOB_TIMEOUT_SECONDS` | `3600` | Полное задание |
| `AI_CORE_RESULT_DOWNLOAD_TTL_SECONDS` | `86400` | Доступность результатов |
| `AI_CORE_MAX_ATTEMPTS_PER_IMAGE` | `3` | Попытки одного результата |
| `AI_CORE_MAX_ACTIVE_JOBS` | `100` | Одновременные задания |
| `AI_CORE_ARTIFACT_SERVICE_URL` | обязательно | Служба файлов |
| `AI_CORE_ARTIFACT_SERVICE_TOKEN` | секрет | Токен службы файлов |

`lease_expires_at = created_at + queue_budget + attempt_timeout`.

## Служба временных файлов

| Переменная | Значение | Назначение |
| --- | ---: | --- |
| `AI_CORE_ARTIFACT_SERVICE_TOKEN` | секрет | Токен внутренних клиентов |
| `AI_CORE_TEMP_STORAGE_ENDPOINT` | обязательно | Адрес S3 |
| `AI_CORE_TEMP_STORAGE_BUCKET` | обязательно | Корзина |
| `AI_CORE_TEMP_STORAGE_REGION` | обязательно | Регион |
| `AI_CORE_TEMP_STORAGE_ACCESS_KEY` | секрет | Ключ временной корзины |
| `AI_CORE_TEMP_STORAGE_SECRET_KEY` | секрет | Секрет временной корзины |
| `AI_CORE_ARTIFACT_URL_TTL_SECONDS` | `900` | Короткая ссылка |
| `AI_CORE_ARTIFACT_TTL_SECONDS` | `90000` | Жизнь объекта |
| `AI_CORE_ARTIFACT_MAX_SIZE_BYTES` | `15728640` | Размер файла |

## Воркер

| Переменная | Значение | Назначение |
| --- | ---: | --- |
| `AI_CORE_WORKER_TYPE` | обязательно | Тип воркера |
| `AI_CORE_WORKER_COMMAND_QUEUE` | обязательно | Очередь команд |
| `AI_CORE_WORKER_RESULT_QUEUE` | обязательно | Очередь результатов |
| `AI_CORE_WORKER_CONCURRENCY` | `1` | Параллельные команды |

Ключи S3 воркерам не выдаются.

## Воркер модели

| Переменная | Значение | Назначение |
| --- | ---: | --- |
| `AI_CORE_MODEL_NAME` | обязательно | Модель |
| `AI_CORE_MODEL_VERSION` | обязательно | Версия |
| `AI_CORE_MODEL_TIMEOUT_SECONDS` | `600` | Вызов модели |

Из 900 секунд попытки: до 600 — модель; 300 — чтение, запись и публикация.

## Воркер уведомлений

| Переменная | Значение | Назначение |
| --- | ---: | --- |
| `AI_CORE_STATUS_CALLBACK_URL` | обязательно | Адрес основного сервера |
| `AI_CORE_STATUS_CALLBACK_SECRET` | секрет | HMAC-секрет |
| `AI_CORE_STATUS_CALLBACK_TIMEOUT_SECONDS` | `10` | Один HTTP-запрос |
| `AI_CORE_STATUS_CALLBACK_MAX_ATTEMPTS` | `10` | Попытки доставки |
