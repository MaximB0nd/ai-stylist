# Договор воркера проверки

Имена очередей и оболочка сообщения определены в
[реестре сообщений](../../../messaging.md#очереди-воркеров). Поле `outfit_spec`
соответствует единственной схеме
[`OutfitSpec`](../../../models.md#outfitspec-версии-1).

## Команда

| Поле | Тип |
| --- | --- |
| `prepared_inputs` | Объект `face` и `body` с `artifact_id`, короткой `read_url`, `expires_at` и описанием файла |
| `candidate` | Объект с `artifact_id`, короткой `read_url`, `expires_at` и описанием результата генерации |
| `outfit_spec` | [`OutfitSpec`](../../../models.md#outfitspec-версии-1) |
| `policy_version` | Строка точной версии политики |

Смысл и срок файловых ссылок определены только в
[правилах временных файлов](../../../artifacts.md#запись-и-чтение).

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

Отсутствующая обязательная проверка даёт `INCONCLUSIVE`. Окончательные ошибки:
`INVALID_CANDIDATE`, `UNSUPPORTED_POLICY`. Временные: `MODEL_UNAVAILABLE`,
`INPUT_UNAVAILABLE`.
