# Договор воркера очистки

## Очереди

- команды: `ai.worker.temporary.cleanup.commands`;
- результаты: `ai.worker.temporary.cleanup.results`.

Сообщение использует [общую оболочку](../../message-contracts.md).

## Полезная нагрузка команды

```json
{
  "reason": "JOB_COMPLETED",
  "object_keys": [
    "temporary/job-id/prepared/face.webp",
    "temporary/job-id/3/2/candidate.webp"
  ]
}
```

## Полезная нагрузка результата

```json
{
  "status": "SUCCEEDED",
  "deleted_count": 2,
  "missing_count": 0,
  "failed_keys": []
}
```

Ключ вне разрешённой временной области отклоняется с кодом `FORBIDDEN_KEY`.
Отсутствующий объект считается успешно очищенным. `STORAGE_UNAVAILABLE` является
временной ошибкой. Договор никогда не разрешает удаление постоянного альбома.
