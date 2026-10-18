# Договор службы-стилиста

`POST /v1/style` принимает JSON по [общему договору](../CONTRACT.md). В MVP
токены авторизации не проверяются. Запрос содержит `request_id`, приведённые
`person` и `preferences` из внешнего договора, `color_type` (`spring`, `summer`,
`autumn`, `winter`) и массив `reserved_outfit_hashes` (SHA-256 ранее выбранных
комплектов этого задания). Другие поля запрещены.

HTTP `200` содержит тот же `request_id`, непустой объект `outfit_spec`,
непустую строку `outfit_spec_version`, а также `model_version` и
`prompt_version`. Служба не резервирует комплект. Оркестратор вычисляет
SHA-256 приведённого JSON `{outfit_spec_version, outfit_spec}` и отклоняет
дубликат внутри задания. Временные и окончательные ошибки используют Problem
Details общего договора.
