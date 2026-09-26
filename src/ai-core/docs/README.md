# Документация AI Core

Документы разделены по границе доступа:

- [public](public/README.md) — всё, что должен знать основной сервер;
- [internal](internal/README.md) — устройство и реализация AI Core.

## Единственные источники истины

| Сведения | Главный документ |
| --- | --- |
| Внешние запросы, ответы, состояния и уведомления | [public/CONTRACT.md](public/CONTRACT.md) |
| Общая внутренняя архитектура | [internal/architecture.md](internal/architecture.md) |
| Очереди, оболочка сообщений и доставка | [internal/messaging.md](internal/messaging.md) |
| Владение состоянием, таблицы и восстановление | [internal/state.md](internal/state.md) |
| Переменные окружения | [internal/configuration.md](internal/configuration.md) |
| Работа с чувствительными и временными данными | [internal/data-policy.md](internal/data-policy.md) |
| Журналы, показатели и готовность служб | [internal/operations.md](internal/operations.md) |
| Модели, `OutfitSpec` и правила проверки | [internal/models.md](internal/models.md) |
| Структура `OutfitSpec` | [internal/schemas/outfit-spec-v1.schema.json](internal/schemas/outfit-spec-v1.schema.json) |
| Справочник одежды версии 1 | [internal/taxonomies/outfit-v1.json](internal/taxonomies/outfit-v1.json) |
| Сравнение моделей и нагрузочная проверка | [internal/model-benchmark.md](internal/model-benchmark.md) |
| Последовательность реализации | [internal/roadmap.md](internal/roadmap.md) |

Документы служб ссылаются на эти файлы и не копируют общие правила.
