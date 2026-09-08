6. Retrieve Album (Frontend $\rightarrow$ Core Backend)

Fetches album details and dynamically generated presigned URLs for viewing and downloading all 10 images.

Method: GET

URL: /api/v1/albums/{album_id}

Headers:
- Authorization: Bearer <access_token>

Responses

200 OK

```JSON
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Office",
  "situation": "office",
  "styles": ["minimalism", "classic"],
  "shoes": ["loafers"],
  "impressions": ["confident", "elegant"],
  "created_at": "2026-09-05T10:15:30Z",
  "is_archived": false,
  "total_photos": 10,
  "photos": [
    {
      "id": "11111111-28b9-48cb-9964-6d9b4db7be8d",
      "order_index": 0,
      "url": "https://stylist.example.com/media/albums/3fa85f64/look_00.webp?X-Amz-Signature=89abc..."
    },
    {
      "id": "22222222-28b9-48cb-9964-6d9b4db7be8d",
      "order_index": 1,
      "url": "https://stylist.example.com/media/albums/3fa85f64/look_01.webp?X-Amz-Signature=def01..."
    }
  ]
}
```

403 Forbidden — Accessing an album owned by another user.

404 Not Found — Album not found or permanently deleted.
