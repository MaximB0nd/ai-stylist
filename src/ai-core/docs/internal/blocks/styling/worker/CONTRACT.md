# Договор воркера-стилиста

Имена очередей и оболочка сообщения определены в
[реестре сообщений](../../../messaging.md#очереди-воркеров). Структура каждого
кандидата определяется только в
[`OutfitSpec`](../../../models.md#outfitspec-версии-1).

```json
{
  "person": {
    "age": 26,
    "height_cm": 172,
    "gender": "female"
  },
  "preferences": {
    "occasion": "office",
    "styles": ["classic", "minimalism"]
  },
  "outfit_schema_version": "1.0",
  "taxonomy_version": "1.0",
  "excluded_outfit_hashes": ["sha256:example"],
  "candidate_count": 3,
  "seed": 12345
}
```

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

Остальные поля каждого элемента `candidates` задаются нормативной схемой.
Окончательные ошибки: `INVALID_PROFILE`, `UNSUPPORTED_TAXONOMY`,
`NO_VALID_OUTFIT`. Временные: `MODEL_UNAVAILABLE`, `MODEL_OVERLOADED`.
