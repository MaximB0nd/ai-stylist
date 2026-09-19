# Authentication & Authorization Architecture (`backend_core`)

## Overview

This document describes the architectural decisions, layer separation, database modeling, and authentication mechanisms implemented for the **AI Stylist** `backend_core` service.

---

## 1. Architectural Layers & Separation of Concerns

The service strictly adheres to layered architecture and the KISS principle:

```text
HTTP Request
     │
     ▼
[Controller Layer] (app/api/v1/endpoints/auth.py)
  - HTTP routing, request deserialization, status codes (201, 200)
  - Depends on AuthService via FastAPI dependency injection
     │
     ▼
[Service Layer] (app/services/auth_service.py)
  - Pure domain business logic
  - Conflict checking (409 on duplicate email)
  - Password hashing & verification
  - JWT generation & credential verification
  - No direct SQL queries
     │
     ▼
[Database / Repository Layer] (app/db/repositories/user_repository.py)
  - Direct database queries via SQLAlchemy 2.0 AsyncSession
  - User retrieval by ID and by normalized email
  - User persistence
     │
     ▼
[Database Engine] (PostgreSQL 16 via asyncpg)
```

---

## 2. Component Breakdown

| Directory / File | Layer | Responsibility |
|---|---|---|
| `app/core/config.py` | Core | Centralized application settings (`pydantic-settings`) loaded from environment variables (`SECRET_KEY`, `ALGORITHM`, `DATABASE_URL`). |
| `app/core/security.py` | Core / Security | Password hashing with `bcrypt` (truncated to 72 bytes per spec) and JWT encoding/decoding with `python-jose`. |
| `app/core/dependencies.py` | Core / DI | FastAPI dependency providers for `AsyncSession`, `UserRepository`, `AuthService`, and `get_current_user` (Bearer token extractor). |
| `app/models/base.py` | Models | SQLAlchemy 2.0 `DeclarativeBase`. |
| `app/models/user.py` | Models | ORM model for `users` table per `DB_STRUCTURE.md` specifications. |
| `app/models/album.py` | Models | ORM model for `albums` table related to `User`. |
| `app/models/photo.py` | Models | ORM model for `photos` table related to `Album`. |
| `app/db/session.py` | Database | Asynchronous engine setup (`create_async_engine`) and session generator (`get_db`). |
| `app/db/repositories/user_repository.py` | Repository | Data access abstraction for `User` entities with asynchronous queries (`select`). |
| `app/schemas/auth.py` | Schemas (DTO) | Pydantic v2 schemas: `UserRegisterRequest`, `UserLoginRequest`, `TokenResponse`, and `UserResponse`. |
| `app/services/auth_service.py` | Domain Service | Business logic for registration and authentication workflows. |
| `app/api/v1/endpoints/auth.py` | Controllers | REST endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, and `GET /api/v1/auth/me`. |
| `app/api/v1/router.py` | Routing | Aggregates all v1 feature routers. |
| `app/main.py` | Application Entrypoint | FastAPI application instance, CORS middleware, and custom validation error handler (mapping to 400 Bad Request). |

---

## 3. Endpoints & API Contracts

### 3.1. Registration (`POST /api/v1/auth/register`)
- **Input:** `{"name": "Anna", "email": "user@example.com", "password": "SecurePassword123!"}`
- **Success Response (201 Created):**
  ```json
  {
    "access_token": "<jwt_string>",
    "token_type": "bearer",
    "id": "<user_uuid>"
  }
  ```
- **Errors:**
  - `400 Bad Request`: Invalid email format or password shorter than 8 characters.
  - `409 Conflict`: An account with this email address already exists.

### 3.2. Login (`POST /api/v1/auth/login`)
- **Input:** `{"email": "user@example.com", "password": "SecurePassword123!"}`
- **Success Response (200 OK):**
  ```json
  {
    "access_token": "<jwt_string>",
    "token_type": "bearer",
    "id": "<user_uuid>"
  }
  ```
- **Errors:**
  - `401 Unauthorized`: Invalid email or password.

### 3.3. Current User (`GET /api/v1/auth/me`)
- **Headers:** `Authorization: Bearer <access_token>`
- **Success Response (200 OK):**
  ```json
  {
    "id": "<user_uuid>",
    "email": "user@example.com",
    "name": "Anna",
    "is_active": true,
    "created_at": "2026-09-10T12:00:00Z"
  }
  ```
- **Errors:**
  - `401 Unauthorized`: Missing, invalid, or expired token.

---

## 4. Key Technical Decisions

1. **Native `bcrypt` instead of `passlib`:**
   - In Python 3.12+, `passlib 1.7.4` has known incompatibility bugs with `bcrypt >= 4.0.0` (accessing removed attribute `__about__` and failing on 72-byte passwords). Using the `bcrypt` library directly eliminates external monkeypatching, adheres to KISS, and provides fast, secure password hashing.
2. **Strict Validation Error Status (HTTP 400):**
   - By default, FastAPI/Starlette returns `422 Unprocessable Entity` on Pydantic validation errors. A custom exception handler for `RequestValidationError` was registered for `/api/v1/auth/*` to return `400 Bad Request` in strict compliance with `REGISTRATION.md`.
3. **Database Independence for Service & Controller Layers:**
   - Endpoints depend only on `AuthService`. `AuthService` depends only on `UserRepository`. `UserRepository` handles SQL operations. This allows unit testing via mocks or fake in-memory repositories without requiring an active PostgreSQL instance during lightweight test runs.
