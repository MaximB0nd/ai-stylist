# Служба API

Служба API — единственная внешняя точка входа AI Core. Она проверяет
аутентификацию и формат HTTP-запроса, затем вызывает главный оркестратор через его
внутренний договор.

Служба не хранит состояние задания и не читает базы внутренних служб. Её можно
запускать в нескольких одинаковых копиях за балансировщиком.

- Внешний договор: [../CONTRACT.md](../CONTRACT.md)
- Внутренняя операция главного оркестратора:
  [../../internal/blocks/orchestration/main-orchestrator/CONTRACT.md](../../internal/blocks/orchestration/main-orchestrator/CONTRACT.md)
- Общие эксплуатационные правила: [../../internal/operations.md](../../internal/operations.md)
