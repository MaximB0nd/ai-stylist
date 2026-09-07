1. User Registration

Creates a new user account and immediately returns a JWT token for seamless auto-login.
Method: POST 
URL: /api/v1/auth/register

    Headers: Content-Type: application/json

Request Body
```JSON

{
  "name": "Anna",
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

Responses
201 Created

JSON
```
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "id": "7b5b294e-28b9-48cb-9964-6d9b4db7be8d"
  }
}
```
400 Bad Request — Invalid email format or weak password.

409 Conflict — An account with this email address already exists.