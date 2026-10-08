# Договор службы генерации

`POST /v1/generate` принимает JSON по [общему договору](../CONTRACT.md). В MVP
токены авторизации не проверяются. Запрос содержит `request_id`, `face_image`
и `body_image` (каждый с `read_url` и `checksum_sha256`),
`outfit_spec_version`, непустой `outfit_spec`, целочисленный `seed` и `output`
с `write_url` службы файлов. Другие поля запрещены. Служба записывает один кандидат
через artifact service и отвечает только после успешной публикации.

HTTP `200` содержит тот же `request_id`, `artifact` с `checksum_sha256`,
`media_type`, `size_bytes`, `width`, `height`, а также `model_version` и
`prompt_version`. Ошибки используют Problem Details общего договора. Каждая
новая принятая попытка записи получает от оркестратора новый `request_id` и
новое место записи; результат старой попытки не перезаписывается.
