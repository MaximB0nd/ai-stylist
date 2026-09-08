2. User Authentication (Login)

Verifies user credentials and issues a JWT token.  
Method: POST

URL: /api/v1/auth/login

Headers: Content-Type: application/jsonRequest Body


```JSON
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```


Responses

200 OK

```JSON
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "id": "7b5b294e-28b9-48cb-9964-6d9b4db7be8d"
}
```

401 Unauthorized — Invalid email or password.