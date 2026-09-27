# Договор службы доступа к временным файлам

Служба доступна только внутренним службам AI Core по HTTPS и принимает
`Authorization: Bearer <artifact-service-token>`. Она не имеет собственной базы:
место объекта однозначно определяется по `artifact_id`.

## Получение ссылок

```text
POST /internal/v1/artifacts/{artifact_id}/access
```

```json
{
  "operation": "WRITE",
  "content_type": "image/webp",
  "max_size_bytes": 15728640
}
```

```json
{
  "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9B1",
  "url": "https://temporary-files.example/opaque-token",
  "expires_at": "2026-09-27T12:00:00Z"
}
```

`operation` принимает `READ` или `WRITE`. Ссылка даёт доступ только к одному
объекту и одной операции. Повторный запрос обновляет ссылку того же файла. Срок
ссылки не может выходить за предельный срок жизни объекта. Главный оркестратор
не запрашивает ссылки после закрытия или истечения срока файла.

## Удаление

```text
DELETE /internal/v1/artifacts/{artifact_id}
```

Успешный ответ — `204 No Content`. Операция идемпотентна: отсутствующий объект
также возвращает `204`.

## Готовность

```text
GET /internal/ready
```

Служба готова, когда проверены настройки и доступно временное хранилище.
