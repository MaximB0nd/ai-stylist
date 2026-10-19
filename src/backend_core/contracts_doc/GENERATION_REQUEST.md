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

Оба файла: не более 10 МиБ каждый, один кадр, стороны не более 4096 пикселей.
Backend проверяет декодирование и соответствие MIME содержимому, исправляет
ориентацию, удаляет метаданные и сохраняет исходники как 8-битные PNG.
AI Core получает ссылки на `.png` с `Content-Type: image/png`.
Готовый PNG не должен превышать 15 МиБ; автоматического уменьшения разрешения нет.
Подробности: `docs/image_normalization.md`.

Остальные поля:
- `age`: `26` (целое число от 16 до 100 включительно)
- `height`: `172` (целое число, в см)
- `gender`: `"f"` или `"m"` (пол: female / male)
- `situation`: `"office"` (ровно 1 значение: `"street"`, `"study"`, `"office"`, `"evening"`)
- `styles`: `"minimal"` (ровно 1 значение: `"minimal"`, `"classic"`, `"casual"`, `"romantic"`). Старое значение `"minimalism"` принимается как алиас и передаётся в AI Core как `"minimal"`. Значения `"sport"` и `"streetwear"` не поддерживаются актуальным договором AI Core и отклоняются до создания задачи.
- `shoes`: `"loafers"` (ровно 1 значение: `"sneakers"`, `"loafers"`, `"heels"`, `"boots"`)
- `impressions`: `"confident"` (ровно 1 значение: `"confident"`, `"elegant"`, `"relaxed"`, `"bright"`)

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
- `400 Bad Request` — Повреждённое изображение, несовпадение MIME, анимация или недопустимые размеры/разрядность.
- `413 Content Too Large` — Исходный файл больше 10 МиБ или итоговый PNG больше 15 МиБ.
- `422 Unprocessable Entity` — Не предоставлены обе обязательные фотографии.
