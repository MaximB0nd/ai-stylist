# Docker & Docker Compose Setup

This document describes the containerization and orchestration setup for the **AI Stylist** services.

---

## 1. Overview

The project uses Docker Compose to orchestrate the infrastructure and backend services in isolated containers connected via an internal bridge network (`stylist-net`):

```text
[Client / Browser]
       │
       │ :8000 (HTTP / Swagger)
       ▼
┌──────────────────────────────────────┐
│ stylist-backend-core (FastAPI)       │
│  - Python 3.12-slim                  │
│  - SQLAlchemy 2.0 + asyncpg          │
└──────────────────┬───────────────────┘
                   │
                   │ :5432 (Internal Network: db:5432)
                   ▼
┌──────────────────────────────────────┐
│ stylist-db (PostgreSQL 16)           │
│  - postgres:16-alpine                │
│  - Volume: postgres_data             │
│  - Auto-init: db/init.sql            │
└──────────────────────────────────────┘
```

---

## 2. Services Breakdown

### 2.1. `db` (PostgreSQL 16)
- **Image:** `postgres:16-alpine`
- **Port:** `5432` mapped to host `localhost:5432`.
- **Initialization:** Mounts [src/backend_core/db/init.sql](file:///c:/Users/ivan2/ai-stylist/src/backend_core/db/init.sql) into `/docker-entrypoint-initdb.d/init.sql:ro`. On first run, it automatically creates:
  - `pgcrypto` extension for UUID generation.
  - `users`, `albums`, `photos` tables per `DB_STRUCTURE.md`.
  - All associated indexes and foreign key constraints.
- **Persistence:** Uses a named volume `postgres_data` mapped to `/var/lib/postgresql/data`.
- **Healthcheck:** Verifies readiness via `pg_isready`.

### 2.2. `backend_core` (FastAPI Service)
- **Build Context:** [src/backend_core](file:///c:/Users/ivan2/ai-stylist/src/backend_core) using [Dockerfile](file:///c:/Users/ivan2/ai-stylist/src/backend_core/Dockerfile).
- **Port:** `8000` mapped to host `localhost:8000`.
- **Database Connection:** Connects to PostgreSQL using internal service hostname:
  ```text
  postgresql+asyncpg://postgres:postgres@db:5432/stylist
  ```
- **Dependency Management:** Waits for `db` container to become healthy before starting.
- **Development Mount:** Mounts `./src/backend_core/app:/app/app` for hot code reloading during development.

---

## 3. Quick Start & Common Commands

### Start All Services
```bash
docker compose up -d --build
```

### View Logs
```bash
docker compose logs -f backend_core
docker compose logs -f db
```

### Access Application & Documentation
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Healthcheck:** [http://localhost:8000/health](http://localhost:8000/health)

### Stop Services
```bash
docker compose down
```

### Stop Services & Wipe Data (Clean Reset)
```bash
docker compose down -v
```
