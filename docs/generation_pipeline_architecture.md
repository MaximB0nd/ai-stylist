# Сценарий интеграции генерации

Единое руководство для любого backend находится в
[документации AI Core](../src/ai-core/docs/public/ai-core-api/README.md).

1. Разместить две исходные фотографии по доступным временным HTTP-ссылкам.
2. Прочитать capabilities и отправить JSON на `POST /v1/jobs` с `Idempotency-Key`.
3. Сохранить `job_id`; опрашивать `GET /v1/jobs/{job_id}`.
4. Для `COMPLETED/AVAILABLE` скачать ровно запрошенное число файлов по полученным URL.
5. Проверить SHA-256 и постоянно сохранить все файлы.
6. Отправить ACK без тела и получить `204`.

Состояния AI Core: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED`.
Дополнительные состояния собственного приложения не являются состояниями AI Core.
Webhook/callback не используется. Формат результата определяется метаданными;
нельзя предполагать фиксированные десять изображений или обязательный WebP.

- [Запросы, ответы и доставка](../src/ai-core/docs/public/ai-core-api/CONTRACT.md)
- [Ошибки и повторы](../src/ai-core/docs/public/ai-core-api/ERRORS.md)
- [Требования к ссылкам и хранению](minio_and_integration.md)
