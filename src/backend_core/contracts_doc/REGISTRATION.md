# 1. Регистрация пользователя

Создает новую учетную запись пользователя и сразу возвращает JWT-токен для автоматического входа в систему.

- **Метод:** `POST`
- **URL:** `/api/v1/auth/register`
- **Заголовки:** `Content-Type: application/json`

## Тело запроса (Request Body)

```json
{
  "name": "Анна",
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

## Ответы (Responses)

### `201 Created`
Учетная запись успешно создана:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "id": "7b5b294e-28b9-48cb-9964-6d9b4db7be8d"
}
```

### Ошибки:
- `400 Bad Request` — Неверный формат email или слабый пароль.
- `409 Conflict` — Пользователь с таким email уже существует.