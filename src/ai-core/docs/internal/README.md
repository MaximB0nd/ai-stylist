# Внутренняя документация AI Core

| Раздел | Документ |
| --- | --- |
| Архитектура | [architecture/README.md](architecture/README.md) |
| Порядок реализации | [architecture/roadmap.md](architecture/roadmap.md) |
| Сообщения | [runtime/messaging.md](runtime/messaging.md) |
| Состояние | [runtime/state.md](runtime/state.md) |
| Временные файлы | [runtime/artifacts.md](runtime/artifacts.md) |
| Данные | [runtime/data-policy.md](runtime/data-policy.md) |
| Эксплуатация | [runtime/operations.md](runtime/operations.md) |
| Модели | [models/README.md](models/README.md) |
| Проверка моделей | [models/benchmark.md](models/benchmark.md) |
| Службы | [services/README.md](services/README.md) |

## Правила

- Главный оркестратор владеет ходом задания.
- Processing services не вызывают друг друга и не читают PostgreSQL.
- Оркестратор вызывает processing services по внутреннему HTTP.
- Processing services не зависят от оркестратора или очереди сообщений.
- Байты изображений не проходят через внешний интерфейс или оркестратор.
- Каждая служба разворачивается отдельно.
