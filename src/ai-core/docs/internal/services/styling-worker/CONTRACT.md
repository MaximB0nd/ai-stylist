# Договор воркера-стилиста

Оболочка и очереди: [messaging.md](../../messaging.md).

## Команда

```json
{
  "person": {
    "age": 26,
    "height_cm": 172,
    "gender": "female"
  },
  "preferences": {
    "occasion": "office",
    "styles": ["classic", "minimalism"],
    "shoes": ["loafers"],
    "impressions": ["confident", "elegant"],
    "description": "Сдержанные образы для офиса"
  },
  "outfit_schema_version": "1.0",
  "excluded_outfit_hashes": ["sha256:example"],
  "candidate_count": 3,
  "seed": 12345
}
```

## Результат

```json
{
  "status": "SUCCEEDED",
  "model_version": "qwen3.5-4b@example",
  "prompt_version": "stylist-v1",
  "candidates": [
    {
      "schema_version": "1.0",
      "outfit_id": "f883f0d6-61bf-432d-9bed-074d912db2f0"
    }
  ]
}
```

Полный элемент `candidates`: [`OutfitSpec`](../../models.md#outfitspec-версии-1).

| Код | Повтор |
| --- | --- |
| `INVALID_PROFILE`, `NO_VALID_OUTFIT` | нет |
| `MODEL_UNAVAILABLE`, `MODEL_OVERLOADED` | да |

Ошибка и отмена: [общий результат](../../messaging.md#результат-воркера).
