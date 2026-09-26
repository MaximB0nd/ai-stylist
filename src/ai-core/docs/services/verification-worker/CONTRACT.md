# Договор воркера проверки результата

## Очереди

- команды: `ai.worker.image.verify.commands`;
- результаты: `ai.worker.image.verify.results`.

Сообщение использует [общую оболочку](../../message-contracts.md).

## Полезная нагрузка команды

```json
{
  "face_photo_url": "https://storage.example/prepared-face",
  "body_photo_url": "https://storage.example/prepared-body",
  "candidate_url": "https://storage.example/candidate",
  "outfit_spec": {
    "schema_version": "1.0",
    "outfit_id": "f883f0d6-61bf-432d-9bed-074d912db2f0"
  },
  "policy_version": "verification-v1"
}
```

## Полезная нагрузка результата

```json
{
  "status": "SUCCEEDED",
  "decision": "ACCEPTED",
  "policy_version": "verification-v1",
  "scores": {
    "face_similarity": 0.91,
    "full_body": 0.98,
    "outfit_match": 0.89,
    "quality": 0.87
  },
  "reason_codes": []
}
```

`decision` принимает `ACCEPTED`, `REJECTED` или `INCONCLUSIVE`. Отсутствующая
обязательная проверка даёт `INCONCLUSIVE`, а не успех. Временные коды ошибок:
`MODEL_UNAVAILABLE`, `STORAGE_UNAVAILABLE`; окончательные: `INVALID_CANDIDATE`,
`UNSUPPORTED_POLICY`.
