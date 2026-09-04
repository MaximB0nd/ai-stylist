# AGENTS.md — Stylist Backend Service Guidelines

## 1. Project Overview & Scope
This service is the core managing backend for the **"AI Stylist" MVP** mobile-first web application.
It orchestrates user authentication, generation questionnaires, photo uploads, generation task lifecycles, album management, asynchronous AI service communication, and secure media access.

### Architectural Boundaries:
- **Core Backend (FastAPI - this service):** Business logic, JWT authentication, PostgreSQL metadata persistence, MinIO object storage management, generation task orchestration, and AI service webhooks.
- **Infrastructure:** Nginx (Reverse Proxy & Gateway) + PostgreSQL 16 + MinIO + FastAPI orchestrated via Docker Compose.

---

## 2. Tech Stack & Standards
- **Runtime:** Python 3.12+
- **Framework:** FastAPI (strictly asynchronous: `async`/`await`)
- **Validation & Settings:** Pydantic v2, Pydantic Settings
- **ORM & Migrations:** SQLAlchemy 2.0 (asyncio) + `asyncpg` + Alembic
- **Primary Database:** PostgreSQL 16
- **Object Storage:** MinIO Python SDK (S3-compatible API)
- **Security:** JWT (Access/Refresh tokens) + Passlib (bcrypt)
- **HTTP Client:** `httpx` (asynchronous client for AI service dispatch)

---

## 3. Project Directory Structure
Maintain strict separation of concerns through layered architecture:

```text
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       └── router.py
├── core/
├── db/
├── models/                      # SQLAlchemy 2.0 ORM models
├── schemas/                     # Pydantic v2 DTOs (Request/Response validation)
├── services/                    # Business logic domain layer (No DB queries in endpoints)
└── main.py                      # FastAPI app instance, lifespan handlers, CORS, middleware