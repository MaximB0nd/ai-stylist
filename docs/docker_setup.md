# Развертывание через Docker и Docker Compose

В этом документе описана конфигурация контейнеризации и оркестрации сервисов **AI Stylist**.

---

## 1. Архитектурная схема

Проект использует Docker Compose для запуска инфраструктуры и бэкенда в изолированных контейнерах, объединенных внутренней bridge-сетью (`stylist-net`):

```text
[Клиент / Браузер]
       │
       │ :8000 (HTTP / Swagger)
       ▼
┌──────────────────────────────────────┐
│ stylist-backend-core (FastAPI)       │
│  - Python 3.12-slim                  │
│  - Alembic (авто-миграции)           │
│  - SQLAlchemy 2.0 + asyncpg          │
└──────────────────┬───────────────────┘
                   │
                   │ :5432 (внутренняя сеть: db:5432)
                   ▼
┌──────────────────────────────────────┐
│ stylist-db (PostgreSQL 16)           │
│  - postgres:16-alpine                │
│  - Volume: postgres_data             │
│  - DB Engine: PostgreSQL 16          │
└──────────────────────────────────────┘
```

---

## 2. Описание сервисов

### 2.1. `db` (PostgreSQL 16)
- **Образ:** `postgres:16-alpine`
- **Порт:** `5432` проброшен на хост `localhost:5432`.
- **Постоянное хранение:** Использует именованный том `postgres_data`, примонтированный в `/var/lib/postgresql/data`.
- **Проверка готовности (Healthcheck):** Проверяет готовность БД через утилиту `pg_isready`.
- **Автономный SQL-скрипт (при необходимости):** В репозитории доступен файл [../src/backend_core/db/init.sql](../src/backend_core/db/init.sql) для ручной инициализации БД вне Compose (выполняется атомарно в одной транзакции с фиксацией версии Alembic в конце).

### 2.2. `backend_core` (FastAPI-сервис)
- **Контекст сборки:** [../src/backend_core](../src/backend_core) на базе [Dockerfile](../src/backend_core/Dockerfile).
- **Порт:** `8000` проброшен на хост `localhost:8000`.
- **Подключение к БД:** Отдельные параметры (`POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) собираются в безопасный URI через `URL.create()`, что исключает ошибки парсинга спецсимволов в пароле.
- **Безопасность JWT:** Переменная `SECRET_KEY` строго обязательна (`${SECRET_KEY:?...}`). При её отсутствии запуск завершается с ошибкой.
- **Управление схемой БД (Alembic + Baseline):** Alembic является единственным источником истины для создания и изменения таблиц. При старте контейнера выполняется процедура `python -m app.db.baseline && alembic upgrade head`. Скрипт `baseline` валидирует состояние БД: для чистой базы применяется стандартный цикл миграций Alembic; при обнаружении существующей неверсионированной схемы скрипт строго валидирует полный fingerprint схемы (все обязательные таблицы `users`, `albums`, `photos`, колонки, первичные/внешние ключи, уникальные индексы и check constraints ревизии `0001`) перед установкой метки `0001`, а при частичной или несовместимой схеме аварийно завершает запуск с ошибкой.
- **Монтирование каталогов:** Каталоги `./src/backend_core/app` и `./src/backend_core/alembic` монтируются в контейнер для мгновенного применения правок кода (hot-reload через `--reload`).

---

## 3. Быстрый старт и основные команды

### Настройка переменных окружения
Перед запуском создайте файл `.env` в корне проекта (на основе `.env.example`):
```bash
cp .env.example .env
```
Задайте свой секретный ключ для `SECRET_KEY` (например, сгенерировав через `openssl rand -hex 32`).

### Запуск всех сервисов
```bash
docker compose up -d --build
```

### Просмотр логов
```bash
docker compose logs -f backend_core
docker compose logs -f db
```

### Управление миграциями Alembic
- **Применить миграции:**
  ```bash
  docker compose exec backend_core alembic upgrade head
  ```
- **Создать новую миграцию:**
  ```bash
  docker compose exec backend_core alembic revision --autogenerate -m "описание_изменений"
  ```

### Доступ к приложению и документации
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Healthcheck:** [http://localhost:8000/health](http://localhost:8000/health)

### Остановка сервисов
```bash
docker compose down
```

### Остановка с удалением томов (полная очистка данных)
```bash
docker compose down -v
```
