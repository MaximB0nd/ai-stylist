# Микросервисы AI Core

Каждый пункт ниже является отдельной единицей сборки и развёртывания. В каждой
функциональной группе есть свой оркестратор и несколько одинаковых воркеров,
которые можно запускать на разных хостах.

| Микросервис | Назначение | Договор | Основной ресурс |
| --- | --- | --- | --- |
| [Служба API](api-service/README.md) | Внешний программный интерфейс AI Core | [CONTRACT](api-service/CONTRACT.md) | Процессор |
| [Главный оркестратор](orchestrator-service/README.md) | Состояние и управление всем конвейером | [CONTRACT](orchestrator-service/CONTRACT.md) | Процессор, PostgreSQL |
| [Оркестратор подготовки](photo-preparation-orchestrator/README.md) | Управление попытками подготовки | [CONTRACT](photo-preparation-orchestrator/CONTRACT.md) | Процессор, PostgreSQL |
| [Подготовка фотографий](photo-preparation-worker/README.md) | Проверка и нормализация исходников | [CONTRACT](photo-preparation-worker/CONTRACT.md) | Процессор, возможно GPU |
| [Оркестратор стилиста](stylist-orchestrator/README.md) | Управление попытками подбора комплектов | [CONTRACT](stylist-orchestrator/CONTRACT.md) | Процессор, PostgreSQL |
| [AI-стилист](stylist-worker/README.md) | Создание `OutfitSpec` | [CONTRACT](stylist-worker/CONTRACT.md) | GPU |
| [Оркестратор генерации](image-generation-orchestrator/README.md) | Управление попытками генерации | [CONTRACT](image-generation-orchestrator/CONTRACT.md) | Процессор, PostgreSQL |
| [Генератор изображения](image-generation-worker/README.md) | Создание кандидата изображения | [CONTRACT](image-generation-worker/CONTRACT.md) | GPU |
| [Оркестратор проверки](verification-orchestrator/README.md) | Управление попытками проверки | [CONTRACT](verification-orchestrator/CONTRACT.md) | Процессор, PostgreSQL |
| [Проверка результата](verification-worker/README.md) | Оценка качества и безопасности | [CONTRACT](verification-worker/CONTRACT.md) | Процессор и GPU |
| [Оркестратор очистки](cleanup-orchestrator/README.md) | Управление очисткой объектов | [CONTRACT](cleanup-orchestrator/CONTRACT.md) | Процессор, PostgreSQL |
| [Очистка](cleanup-worker/README.md) | Удаление временных данных AI Core | [CONTRACT](cleanup-worker/CONTRACT.md) | Процессор, сеть |
| [Оркестратор уведомлений](notification-orchestrator/README.md) | Управление доставкой событий | [CONTRACT](notification-orchestrator/CONTRACT.md) | Процессор, PostgreSQL |
| [Доставка уведомлений](notification-worker/README.md) | Отправка состояний основному серверу | [CONTRACT](notification-worker/CONTRACT.md) | Процессор, сеть |

Общие правила:

- воркеры не вызывают друг друга и не общаются с главным оркестратором;
- главный оркестратор общается только с групповыми оркестраторами;
- каждая группа имеет свои очереди, базу состояния и права доступа;
- воркеры не имеют доступа к базам оркестраторов;
- постоянные файлы принадлежат основному серверу;
- каждый микросервис имеет собственные настройки, журналы, показатели готовности
  и образ для развёртывания;
- одинаковые копии одного микросервиса не отличаются по поведению.
