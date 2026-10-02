# Развертывание через Docker и Docker Compose

В этом документе описана конфигурация контейнеризации и оркестрации сервисов **AI Stylist**.

---

## 1. Архитектурная схема

Проект использует Docker Compose для запуска инфраструктуры, frontend, backend и nginx-gateway в изолированных контейнерах, объединенных внутренней bridge-сетью (`stylist-net`):

```text
[Клиент / Браузер]
       │
       │ :8080 (HTTP)
       ▼
┌──────────────────────────────────────┐
│ stylist-nginx (Reverse Proxy)        │
│  - /api/* -> backend_core:8000       │
│  - /docs, /redoc, /health -> backend │
│  - /* -> frontend:5091               │
└───────────────┬──────────────────────┘
                │
                ├──────────┐
                ▼          ▼
┌──────────────────────┐  ┌──────────────────────────────────────┐
│ stylist-frontend     │  │ stylist-backend-core (FastAPI)       │
│  - Caspian/FastAPI   │  │  - Python 3.12-slim                  │
│  - Port 5091         │  │  - Alembic (авто-миграции)           │
└──────────────────────┘  │  - SQLAlchemy 2.0 + asyncpg          │
                          └──────────────────┬───────────────────┘
                                             │
                                             │ :5432 (db:5432)
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
- **Управление схемой БД (Alembic + Baseline):** Alembic является единственным источником истины для создания и изменения таблиц. При старте контейнера выполняется процедура `python -m app.db.baseline && alembic upgrade head`. Скрипт `baseline` работает по принципу **fail-closed**:
  - Для чистой базы выполняется стандартный цикл миграций Alembic (`0001` -> `head`).
  - Для базы, уже версионированной Alembic, выполняется обычный `upgrade head`.
  - При обнаружении существующей неверсионированной схемы скрипт валидирует полный fingerprint схемы: типы и длины всех колонок, nullability, нормализованные `server_default`, точные первичные ключи `['id']`, внешние ключи с `ON DELETE CASCADE`, уникальные и обычные индексы с точными именами и наборами колонок, а также каноническое выражение check constraint `chk_photos_order_index`. При малейшем несовпадении или ошибках интроспекции запуск немедленно прерывается с ошибкой, а метка версии не выставляется.
  - В качестве альтернативы оператор может в любой момент выполнить явную проверку и однократный ручной stamp: `docker compose exec backend_core alembic stamp 0001`.
- **Монтирование каталогов:** Каталоги `./src/backend_core/app` и `./src/backend_core/alembic` монтируются в контейнер для мгновенного применения правок кода (hot-reload через `--reload`).

### 2.3. `frontend` (Caspian/FastAPI frontend)
- **Контекст сборки:** [../src/frontend](../src/frontend) на базе [Dockerfile](../src/frontend/Dockerfile).
- **Внутренний порт:** `5091`. Наружу напрямую не публикуется; доступен через nginx.
- **Авторизация:** Браузерный код вызывает backend по относительному префиксу `/api/v1`, поэтому в Docker-развертывании не требуется отдельная настройка CORS или внешнего API URL.

### 2.4. `minio` (S3-совместимое объектное хранилище)
- **Контекст сборки:** [../docker/minio](../docker/minio) на базе [Dockerfile](../docker/minio/Dockerfile) (`alpine:3.20` + официальный релиз бинарника MinIO).
- **Порты:** `9000` (S3 API) и `9001` (Web-консоль администрирования).
- **Постоянное хранение:** Том `minio_data:/data`.
- **Авто-инициализация бакетов:** Создание бакета `stylist` выполняется нативно бэкендом при старте приложения через `StorageService._ensure_bucket()` в FastAPI `lifespan`.

### 2.5. `nginx` (Reverse Proxy)
- **Образ:** `nginx:1.27-alpine`.
- **Порт:** По умолчанию публикуется на [http://localhost:8080](http://localhost:8080). Значение можно изменить переменной `NGINX_PORT`.
- **Маршрутизация:** Конфигурация [../nginx/default.conf](../nginx/default.conf) отправляет `/api/*`, `/docs`, `/redoc`, `/openapi.json` и `/health` в backend, а остальные запросы во frontend.

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
- **Frontend через nginx:** [http://localhost:8080](http://localhost:8080)
- **Swagger UI через nginx:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **ReDoc через nginx:** [http://localhost:8080/redoc](http://localhost:8080/redoc)
- **Healthcheck через nginx:** [http://localhost:8080/health](http://localhost:8080/health)
- **Прямой backend-доступ для отладки:** [http://localhost:8000/docs](http://localhost:8000/docs)

### Остановка сервисов
```bash
docker compose down
```

### Остановка с удалением томов (полная очистка данных)
```bash
docker compose down -v
```
