# Внутренняя документация AI Core

| Раздел | Документ |
| --- | --- |
| Архитектура | [architecture.md](architecture.md) |
| Сообщения | [messaging.md](messaging.md) |
| Состояние | [state.md](state.md) |
| Временные файлы | [artifacts.md](artifacts.md) |
| Настройки | [configuration.md](configuration.md) |
| Данные | [data-policy.md](data-policy.md) |
| Эксплуатация | [operations.md](operations.md) |
| Модели | [models.md](models.md) |
| Проверка моделей | [model-benchmark.md](model-benchmark.md) |
| Порядок реализации | [roadmap.md](roadmap.md) |
| Службы | [services/README.md](services/README.md) |
| Договор `OutfitSpec` | [contracts/outfit/schema-v1.json](contracts/outfit/schema-v1.json) |

## Правила

- Главный оркестратор владеет ходом задания.
- Воркеры не вызывают друг друга и не читают PostgreSQL.
- RabbitMQ передаёт команды и результаты, но не хранит состояние задания.
- Байты изображений не проходят через интерфейс, оркестратор или RabbitMQ.
- Каждая служба разворачивается отдельно.
