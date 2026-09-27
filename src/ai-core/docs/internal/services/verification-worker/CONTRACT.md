# Договор воркера проверки

Оболочка и очереди: [messaging.md](../../messaging.md).

## Команда

| Поле | Значение |
| --- | --- |
| `prepared_inputs` | `face`, `body`: `artifact_id`, `read_url`, `expires_at`, метаданные |
| `candidate` | `artifact_id`, `read_url`, `expires_at`, метаданные |
| `outfit_spec` | [`OutfitSpec`](../../models.md#outfitspec-версии-1) |
| `policy_version` | точная версия |

Ссылки: [artifacts.md](../../artifacts.md#доступ).

## Результат

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

Отсутствующая проверка: `INCONCLUSIVE`.

| Код | Повтор |
| --- | --- |
| `INVALID_CANDIDATE`, `UNSUPPORTED_POLICY` | нет |
| `MODEL_UNAVAILABLE`, `INPUT_UNAVAILABLE` | да |

Ошибка и отмена: [общий результат](../../messaging.md#результат-воркера).
