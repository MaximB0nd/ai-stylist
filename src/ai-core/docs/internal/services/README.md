# Службы AI Core

| Служба | Ответственность | Договор |
| --- | --- | --- |
| [Главный оркестратор](main-orchestrator/README.md) | состояние задания и порядок этапов | [CONTRACT.md](main-orchestrator/CONTRACT.md) |
| [Служба временных файлов](artifact-service/README.md) | единственный доступ к временному S3 | [CONTRACT.md](artifact-service/CONTRACT.md) |
| [Воркер подготовки](preparation-worker/README.md) | проверка и нормализация входных фотографий | [CONTRACT.md](preparation-worker/CONTRACT.md) |
| [Воркер-стилист](styling-worker/README.md) | создание вариантов одежды | [CONTRACT.md](styling-worker/CONTRACT.md) |
| [Воркер генерации](generation-worker/README.md) | создание изображения кандидата | [CONTRACT.md](generation-worker/CONTRACT.md) |
| [Воркер проверки](verification-worker/README.md) | проверка изображения кандидата | [CONTRACT.md](verification-worker/CONTRACT.md) |
| [Воркер очистки](cleanup-worker/README.md) | удаление временных файлов | [CONTRACT.md](cleanup-worker/CONTRACT.md) |
| [Воркер уведомлений](notification-worker/README.md) | доставка события состояния | [CONTRACT.md](notification-worker/CONTRACT.md) |
