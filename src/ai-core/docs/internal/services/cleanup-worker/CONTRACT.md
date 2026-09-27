# Договор воркера очистки

Оболочка и очереди: [messaging.md](../../messaging.md).

## Команда

```json
{
  "reason": "RESULTS_ACKNOWLEDGED",
  "artifact_ids": ["01J8Z8Y7W6V5T4S3R2Q1P0N9B1"]
}
```

## Результат

```json
{
  "status": "SUCCEEDED",
  "deleted_count": 1,
  "missing_count": 0,
  "failed_artifact_ids": []
}
```

- Удаление выполняет служба временных файлов.
- Отсутствующий файл считается удалённым.
- Произвольные пути и ключи запрещены.

| Код | Повтор |
| --- | --- |
| `INVALID_ARTIFACT_ID` | нет |
| `ARTIFACT_SERVICE_UNAVAILABLE` | да |

Ошибка и отмена: [общий результат](../../messaging.md#результат-воркера).
