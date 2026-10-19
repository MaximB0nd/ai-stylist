# Модульная карта AI Stylist

Стрелка `A → B` означает зависимость исходного кода A от публичного контракта B. Статус «работает» относится к присутствующему коду; «план» — к документированному компоненту без реализации в этой части репозитория. Карта фиксирует основные части, а не каждый файл.

| Модуль | Ответственность и контракт | Зависит от | Место | Статус | Автор записи |
|---|---|---|---|---|---|
| GenerationPage | Разметка анкеты генерации | SharedLayout | `src/frontend/src/pages/generation.py` | работает | Валаева И. В. |
| GenerationController | Выборы, превью, состояние формы | PhotoSelection, браузерный DOM | `src/frontend/public/js/pages/generation.js` | работает | Валаева И. В. |
| PhotoSelection | Проверить выбор фото и вернуть решение `{file, error}` | нет проектных зависимостей | `src/frontend/public/js/pages/generation.js` | работает | Валаева И. В. |
| SharedLayout | Общий каркас страниц | нет в рамках этой карты | `src/frontend/src/components/shared/layout/` | работает | общая запись |
| Backend API | Пользователи, альбомы и запуск генерации | Storage, AI Core API | `src/backend_core/app/` | работает | общая запись |
| Storage | Хранение исходных и готовых изображений | MinIO API | `src/backend_core/app/services/storage_service.py` | работает | общая запись |
| AI Core API | Договор постановки задач генерации | внутренние службы AI Core | `src/ai-core/docs/public/ai-core-api/` | план | общая запись |

Для участка студентки: `GenerationPage → SharedLayout`; `GenerationController → PhotoSelection`. Импорт `GenerationController → PhotoSelection` пока находится в одном файле `generation.js`, а граница выражена отдельными экспортируемыми функциями и параметром внедрения правила. Точка сборки обычной реализации — вызов `mountGeneration(form)` в `initializeGeneration`; тестовая реализация передаётся через второй аргумент `mountGeneration`. Цикла между этими модулями нет.

Статус AI Core приведён по `src/ai-core/README.md`: в его директории сейчас зафиксированы договоры и архитектура, реализация внешнего интерфейса обозначена как будущая. Карта должна уточняться авторами остальных зон проекта.
