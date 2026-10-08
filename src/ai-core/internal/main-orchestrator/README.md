# Главный оркестратор AI Core

Python 3.12, FastAPI и PostgreSQL. В MVP команды воркерам отправляются по HTTP из
долговечной таблицы `commands`; RabbitMQ и сами воркеры в этот сервис не входят.
Токены авторизации сейчас не проверяются. Ручки следует размещать во внутренней
сети.

## Запуск

Из каталога сервиса:

```sh
python -m venv .venv
.venv/bin/pip install -e .
export ORCHESTRATOR_DATABASE_URL='postgresql+asyncpg://user:password@localhost:5432/orchestrator'
export ORCHESTRATOR_ENCRYPTION_KEY="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

`ORCHESTRATOR_ENCRYPTION_KEY` нужно сохранять между перезапусками: смена ключа
делает незавершённые зашифрованные задания нечитаемыми. Для реальной обработки
настройте `ORCHESTRATOR_ARTIFACT_SERVICE_URL` и JSON-переменную
`ORCHESTRATOR_WORKER_URLS`, например:

```sh
export ORCHESTRATOR_ARTIFACT_SERVICE_URL='http://artifact-service:8000'
export ORCHESTRATOR_WORKER_URLS='{"PREPARATION":"http://preparation:8000","STYLING":"http://styling:8000","GENERATION":"http://generation:8000","VERIFICATION":"http://verification:8000","NOTIFICATION":"http://notification:8000"}'
```

Без службы файлов задания принимаются в `QUEUED` и ждут импорта входных фото.
Для подключения службы после запуска требуется перезапуск оркестратора с её URL.
`GET /internal/ready` отражает готовность PostgreSQL и наличие настройки службы
отдельно.

## Проверка

```sh
docker compose -f compose.test.yml up -d postgres
ORCHESTRATOR_DATABASE_URL='postgresql+asyncpg://test:test@localhost:55439/orchestrator_test' ORCHESTRATOR_ENCRYPTION_KEY=dummy .venv/bin/alembic upgrade head
.venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest -q
```

HTTP-договоры и примеры: [оркестратор](../../docs/internal/services/main-orchestrator/CONTRACT.md),
[команды и callback](../../docs/internal/runtime/http-messaging.md),
[служба файлов](../../docs/internal/services/artifact-service/CONTRACT.md).
