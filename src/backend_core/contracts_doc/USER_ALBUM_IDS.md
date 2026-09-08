7. Retrieve User Album IDs (Frontend $\rightarrow$ Core Backend)

Retrieves all album IDs belonging to the authenticated user. Typically called by the frontend immediately after registration or login to discover existing user albums and load their identifiers into state.

Method: GET

URL: /api/v1/albums

Headers:
- Authorization: Bearer <access_token>

Responses

200 OK

```JSON
{
  "album_ids": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "7b5b294e-28b9-48cb-9964-6d9b4db7be8d"
  ],
  "total": 2
}
```

For newly registered users without any generated albums yet:
```JSON
{
  "album_ids": [],
  "total": 0
}
```

401 Unauthorized — Missing, expired or invalid access token.
