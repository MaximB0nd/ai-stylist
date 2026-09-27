# 3. Запрос на генерацию (Frontend $\rightarrow$ Core Backend)

Принимает две исходные фотографии вместе с параметрами пользователя и ответами на опросник.
Возвращает асинхронный статус принятия задачи (`202 Accepted`), так как процесс генерации занимает время.

- **Метод:** `POST`
- **URL:** `/api/v1/generations`
- **Заголовки:**
  - `Authorization: Bearer <access_token>`
  - `Content-Type: multipart/form-data`

## Поля Form-Data

- `face_photo`: бинарный файл (портрет крупным планом, webp/jpeg/png)
- `body_photo`: бинарный файл (фото в полный рост, webp/jpeg/png)
- `age`: `26` (целое число)
- `height`: `172` (целое число, в см)
- `weight`: `58` (целое число, в кг)
- `situation`: `"office"` (ровно 1 значение: `"street"`, `"study"`, `"office"`, `"evening"`)
- `styles`: `["minimalism", "classic"]` (от 1 до 2 значений: `"minimalism"`, `"classic"`, `"casual"`, `"romantic"`)
- `shoes`: `["loafers"]` (от 1 до 2 значений: `"sneakers"`, `"loafers"`, `"heels"`, `"boots"`)
- `impressions`: `["confident", "elegant"]` (от 1 до 2 значений: `"confident"`, `"elegant"`, `"relaxed"`, `"bright"`)

## Ответы (Responses)

### `202 Accepted`
Задача успешно поставлена в очередь:

```json
{
  "generation_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "VALIDATING",
  "message": "Generation request accepted for processing",
  "status_poll_url": "/api/v1/generations/c84dfb50-f331-4c12-88f5-3c1a3e6015aa/status"
}
```

### Ошибки:
- `400 Bad Request` — Отсутствуют обязательные поля или передано недопустимое значение из перечисления.
- `422 Unprocessable Entity` — Не предоставлены обе обязательные фотографии.
