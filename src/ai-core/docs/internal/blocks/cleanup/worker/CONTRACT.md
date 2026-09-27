# Договор воркера очистки

Имена очередей, издатель команды и оболочка сообщения определены в
[реестре сообщений](../../../messaging.md#очереди-воркеров).

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

Воркер вызывает внутреннюю службу временных файлов. Отсутствующий файл считается
уже удалённым. Воркер не принимает произвольные пути или ключи. Окончательная
ошибка — `INVALID_ARTIFACT_ID`, временная — `ARTIFACT_SERVICE_UNAVAILABLE`.
