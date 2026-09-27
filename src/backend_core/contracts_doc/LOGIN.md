# 2. Аутентификация пользователя (Вход)

Проверяет учетные данные пользователя и выдает JWT-токен доступа.

- **Метод:** `POST`
- **URL:** `/api/v1/auth/login`
- **Заголовки:** `Content-Type: application/json`

## Тело запроса (Request Body)

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

## Ответы (Responses)

### `200 OK`
Успешный вход в систему:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "id": "7b5b294e-28b9-48cb-9964-6d9b4db7be8d"
}
```

### Ошибки:
- `401 Unauthorized` — Неверный адрес электронной почты или пароль.