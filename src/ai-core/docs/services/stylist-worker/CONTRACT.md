# Договор воркера-стилиста

## Очереди

- команды: `ai.worker.outfit.style.commands`;
- результаты: `ai.worker.outfit.style.results`.

Сообщение использует [общую оболочку](../../message-contracts.md).

## Полезная нагрузка команды

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

## Полезная нагрузка успешного результата

```json
{
  "status": "SUCCEEDED",
  "model_version": "qwen3.5-4b@example",
  "prompt_version": "stylist-v1",
  "candidates": [
    {
      "outfit_id": "f883f0d6-61bf-432d-9bed-074d912db2f0",
      "schema_version": "1.0",
      "occasion": "office",
      "style": "classic",
      "items": []
    }
  ]
}
```

Окончательные коды ошибок: `INVALID_PROFILE`, `UNSUPPORTED_TAXONOMY`,
`NO_VALID_OUTFIT`. Временные: `MODEL_UNAVAILABLE`, `MODEL_OVERLOADED`. Кандидат
не считается зарезервированным: это делает главный оркестратор после получения
итога группы.
