# Договор службы проверки кандидата

`POST /v1/verify` принимает JSON по [общему договору](../CONTRACT.md). В MVP
токены авторизации не проверяются. Запрос содержит `request_id`, `face_image`,
`body_image` и `candidate_image` (каждый с `read_url` и `checksum_sha256`),
`outfit_spec_version` и непустой `outfit_spec`. Другие поля запрещены.

HTTP `200` содержит тот же `request_id`, `verdict` (`ACCEPTED`, `REJECTED` или
`INCONCLUSIVE`), массив стабильных `reason_codes` и `policy_version`.
`REJECTED` — завершённая проверка: оркестратор создаёт нового кандидата с тем
же комплектом, не более трёх кандидатов на изображение. `INCONCLUSIVE`
повторяет проверку того же кандидата в пределах лимита попыток. Ошибки
используют Problem Details общего договора.
