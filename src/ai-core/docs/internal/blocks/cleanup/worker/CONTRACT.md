# Договор воркера очистки

Имена очередей, издатель команды и оболочка сообщения определены в
[реестре сообщений](../../../messaging.md#очереди-воркеров).

## Команда

```json
{
  "reason": "RESULTS_ACKNOWLEDGED",
  "targets": [
    {
      "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9B1",
      "delete_url": "https://files.example/delete-once/opaque-token"
    }
  ]
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

Отсутствующий файл считается уже удалённым. Воркер не принимает произвольные
пути или ключи. Окончательная ошибка — `INVALID_DELETE_CAPABILITY`, временная —
`OUTPUT_UNAVAILABLE`.
