# 6. Получение альбома (Frontend $\rightarrow$ Core Backend)

Возвращает детальную информацию об альбоме и динамически сгенерированные presigned-ссылки для просмотра и скачивания всех 10 изображений образов.

- **Метод:** `GET`
- **URL:** `/api/v1/albums/{album_id}`
- **Заголовки:**
  - `Authorization: Bearer <access_token>`

## Ответы (Responses)

### `200 OK`
Альбом успешно найден:

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Офис",
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

### Ошибки:
- `401 Unauthorized` — Отсутствует или недействителен токен доступа.
- `403 Forbidden` — Попытка доступа к альбому другого пользователя.
- `404 Not Found` — Альбом не найден или удален.
