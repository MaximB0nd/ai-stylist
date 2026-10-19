# Внешний HTTP-контракт AI Core v1

## Транспорт и совместимость

Server-to-server HTTP в закрытой сети; запросы и ответы — `application/json`,
кроме скачивания файлов и ответов `204`. Авторизация пользователя остаётся в backend.
API не принимает `user_id`, пользовательский текст, байты фото или `multipart/form-data`.
Неизвестные поля запросов запрещены. Числа передаются JSON-числами, не строками;
логическое значение не заменяет целое число. Повторяющиеся ключи JSON запрещены.

Клиент должен допускать новые поля ответов и неизвестные коды ошибок, сохраняя
безопасный общий сценарий отказа. `message` не является идентификатором ошибки
и не предназначен для прямой локализации пользовательского интерфейса.

## Эндпоинты

| Метод и путь | Успешный ответ |
| --- | --- |
| `GET /v1/capabilities` | `200`, возможности и ограничения |
| `GET /health/live` | `200`, `{"status":"ok"}` |
| `GET /health/ready` | `200`, `{"status":"ok"}` |
| `POST /v1/jobs` | `201`, новое задание; `200`, повтор |
| `GET /v1/jobs/{job_id}` | `200`, состояние задания |
| `POST /v1/jobs/{job_id}/cancel` | `200`, отменённое задание |
| `POST /v1/jobs/{job_id}/results/ack` | `204`, без тела |

`job_id` — UUID. У cancel и ACK тело отсутствует; даже `{}` не допускается.
Неготовность: `GET /health/ready` возвращает `503 {"status":"not_ready"}`
без обязательного `Retry-After`. Проверки здоровья не являются состоянием задания.

## Возможности

`GET /v1/capabilities` доступен независимо от возможности принять задание.
Пример для окружения с необязательным тестом цвета:

```json
{
  "api_version": "v1",
  "requested_image_count": {"minimum": 1, "maximum": 10},
  "input_urls": {"schemes": ["http"], "min_ttl_seconds": 900},
  "person": {
    "age": {"minimum": 1, "maximum": 120},
    "height_cm": {"minimum": 80, "maximum": 240},
    "gender": ["male", "female"]
  },
  "preferences": {
    "occasion": ["street", "study", "office", "evening"],
    "style": ["minimal", "classic", "casual", "romantic"],
    "shoe": ["sneakers", "loafers", "heels", "boots"],
    "mood": ["confident", "elegant", "relaxed", "bright"]
  },
  "color_evidence": {
    "available": true, "optional": true,
    "sources": ["controlled_drape", "self_report"],
    "temperature": ["warm", "neutral", "cool"],
    "depth": ["light", "medium", "deep"],
    "chroma": ["clear", "medium", "muted"],
    "contrast": ["low", "medium", "high"]
  },
  "drape_test": {
    "optional": true,
    "accepted_catalog": null,
    "mutually_exclusive_with": "color_evidence",
    "protocol_version": "aba-v1",
    "drape_set_id": {"pattern": "^[a-z0-9][a-z0-9._-]*$", "maximum_length": 64},
    "drape_set_sha256": {"pattern": "^[0-9a-f]{64}$"},
    "lighting": ["neutral_daylight", "calibrated_5000k"],
    "comparisons": {
      "minimum": 12, "maximum": 24, "minimum_per_axis": 3,
      "passes": ["a", "b", "inconclusive"],
      "directions": {
        "temperature": ["warm", "cool"], "depth": ["light", "deep"],
        "chroma": ["clear", "muted"], "contrast": ["low", "high"]
      }
    }
  }
}
```

TTL берите из текущего ответа. Если `drape_test.optional=false`, полный тест обязателен,
а `color_evidence.available=false`. `accepted_catalog`, когда не `null`, содержит
`drape_set_id` и `drape_set_sha256`: любой переданный тест должен точно совпадать
с ними. Материалы каталога получите у поставщика API; endpoint для их загрузки не определён.

## Создание задания

`POST /v1/jobs`, `Content-Type: application/json`, обязательный
`Idempotency-Key` — непрозрачная непустая строка длиной до 255 символов.

```json
{
  "requested_image_count": 1,
  "inputs": {
    "face": {"url": "http://photos.example/face.png", "expires_at": "2099-01-01T00:00:00Z"},
    "body": {"url": "http://photos.example/body.png", "expires_at": "2099-01-01T00:00:00Z"}
  },
  "person": {"age": 27, "height_cm": 172, "gender": "female"},
  "preferences": {"occasion": "office", "style": "minimal", "shoe": "loafers", "mood": "confident"}
}
```

Пример требует замены URL и сроков и подходит только при необязательном `drape_test`.

| Поле | Ограничение |
| --- | --- |
| `requested_image_count` | обязательное целое `1..10` |
| `inputs.face`, `inputs.body` | обязательные объекты с `url` и `expires_at` |
| `url` | абсолютный HTTP URL до 4096 символов; согласованный origin; без userinfo и fragment |
| `expires_at` | RFC 3339 с часовым поясом; остаток не меньше `input_urls.min_ttl_seconds` |
| `person.age` | обязательное целое `1..120` |
| `person.height_cm` | обязательное целое `80..240` |
| `person.gender` | `male` или `female` |
| `preferences` | все четыре поля обязательны; по одному значению из capabilities |

Временные ссылки должны возвращать сами изображения по GET без дополнительных
заголовков и редиректов. Допустимы JPEG, PNG, однокадровый WebP. Начальные ограничения:
15 MiB на фото, до 4096 пикселей по каждой стороне, 8 бит на канал; ограничения
размера уточняются для окружения и не публикуются в capabilities.
Нужно фото лица и фото полного роста одного человека. Успешное создание задания
не означает, что содержимое фотографий принято: отказ будет виден через GET задания.

Неверные поля, JSON, Content-Type, недостаточный TTL и превышение размера тела
возвращают `400 INVALID_REQUEST`. Начальный предел тела JSON — 65536 байт;
он может отличаться в окружении. Запрещённый origin или схема корректно разобранного
URL возвращают `422 INPUT_URL_NOT_ALLOWED`.

### Дополнительные сведения о цвете

Можно передать один из двух объектов: `color_evidence` или `drape_test`.
Одновременная передача запрещена. При недоступном `color_evidence` используйте полный тест.

```json
{
  "source": "self_report",
  "temperature": "cool",
  "depth": "deep",
  "chroma": "clear",
  "contrast": "high"
}
```

Это значение поля `color_evidence`, не отдельный HTTP-запрос. Все пять полей обязательны;
допустимые значения перечислены в capabilities. `self_report` означает самостоятельную
оценку, `controlled_drape` — результат контролируемого сравнения драпировок.

Для `drape_test` обязательны:

| Поле | Значение |
| --- | --- |
| `protocol_version` | `aba-v1` |
| `drape_set_id` | 1–64 символа, шаблон из capabilities |
| `drape_set_sha256` | 64 строчных hex-символа |
| `lighting` | `neutral_daylight` или `calibrated_5000k` |
| `color_interference_removed` | только `true` |
| `comparisons` | 12–24 пары, минимум три для каждой из четырёх осей |

Каждая пара содержит `pair_id` (1–64 символа, `^[a-z0-9][a-z0-9_-]*$`, уникален),
`axis`, `direction_a`, `direction_b`, `first_pass`, `repeat_pass`.
Оси: `temperature`, `depth`, `chroma`, `contrast`. Направления — противоположные
значения соответствующей оси из capabilities. Выбор при каждом предъявлении:
`a`, `b` или `inconclusive`. Проводите повторное сравнение A–B–A при одинаковом
нейтральном освещении, без макияжа, украшений и цветных отражений от одежды и фона.
Тест может быть признан неубедительным: задание завершится `COLOR_TYPE_UNCERTAIN`.
Полный JSON-пример находится в [examples](../../../examples/README.md).

### Идемпотентность и ответ

Новый ключ создаёт задание (`201`). Тот же ключ и эквивалентное тело возвращают
прежнее задание (`200`); изменённое тело — `409 IDEMPOTENCY_CONFLICT`.
При повторе сохраняйте исходные ключ и тело. Ответ повтора может содержать любое
из состояний задания, а не только `QUEUED`.

```json
{
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "QUEUED",
  "requested_image_count": 1,
  "status_url": "/v1/jobs/c84dfb50-f331-4c12-88f5-3c1a3e6015aa"
}
```

## Получение состояния

`GET /v1/jobs/{job_id}` возвращает `200`, в том числе для `FAILED` и `CANCELLED`.

```json
{
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "PROCESSING",
  "requested_image_count": 1,
  "accepted_image_count": 0,
  "failed_attempt_count": 0,
  "updated_at": "2026-10-19T10:00:00Z",
  "error": null
}
```

| Состояние | Значение | Действие backend |
| --- | --- | --- |
| `QUEUED` | принято, ожидает обработки | продолжать опрос |
| `PROCESSING` | обрабатывается | продолжать опрос |
| `COMPLETED` | запрошенные изображения готовы | проверить состояние доставки |
| `FAILED` | окончательная ошибка | обработать `error` |
| `CANCELLED` | отменено | завершить ожидание |

Последние три состояния конечные. `accepted_image_count` — число принятых результатов,
`failed_attempt_count` — счётчик неудачных попыток, не процент готовности.
Частичные результаты не выдаются. `updated_at` — RFC 3339.
При ошибке `error` содержит `code`, `message`, `retryable` и, возможно, `reasons`.
Без ошибки `error=null`. См. [каталог ошибок](ERRORS.md).

## Результаты

```json
{
  "job_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "COMPLETED",
  "requested_image_count": 1,
  "accepted_image_count": 1,
  "failed_attempt_count": 0,
  "updated_at": "2026-10-19T10:10:00Z",
  "result_delivery_status": "AVAILABLE",
  "results_available_until": "2026-10-20T10:00:00Z",
  "results": [{
    "order_index": 0,
    "artifact_id": "01J8Z8Y7W6V5T4S3R2Q1P0N9M8",
    "download_url": "http://downloads.example/result.png",
    "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "size_bytes": 1048576,
    "format": "png", "width": 1024, "height": 1536,
    "model_version": "image-model@example",
    "prompt_version": "photographer-v1",
    "outfit_spec_version": "1.0", "seed": 12345
  }],
  "error": null
}
```

URL, checksum и метаданные выше иллюстративны. Для реального файла используйте ответ API.
`artifact_id` — непрозрачный идентификатор файла; `order_index` задаёт порядок,
начиная с нуля. Поля версий и `seed` — метаданные результата: сохраняйте как значения,
не стройте по ним логику клиента и не рассчитывайте на возможность воспроизведения.

| Состояние доставки | `results` | Значение |
| --- | --- | --- |
| `AVAILABLE` | ровно `requested_image_count` элементов | скачать до указанного срока |
| `ACKNOWLEDGED` | `[]` | получение уже подтверждено |
| `EXPIRED` | `[]` | срок получения истёк |

Эти поля присутствуют только при `COMPLETED`. После ACK или истечения срока
статус задания остаётся `COMPLETED`. Удалённые результаты не восстанавливаются
обновлением ссылки. При `AVAILABLE` повторный GET возвращает те же адреса до срока.

### Скачивание

Выполняйте GET по `download_url` как по непрозрачному адресу. Не конструируйте путь
из `artifact_id`; hostname и путь могут отличаться от базового адреса API.
Требуется сетевой доступ backend к возвращаемому адресу, дополнительный токен
на уровне этого договора не требуется. Ссылки не предназначены для постоянного
хранения или прямой передачи конечным пользователям.

Обычный GET возвращает `200` и байты изображения. Поддерживается один диапазон
`Range: bytes=...` с ответом `206`; некорректный диапазон — `416`.
Отсутствующий или недоступный по сроку файл возвращает `404`.
Ошибки скачивания имеют `Content-Type: application/problem+json` и поля
`type`, `title`, `status`, `code`, `retryable`, без внешней обёртки `error`.

Сверяйте SHA-256 скачанных байтов с hex-частью `checksum_sha256` после `sha256:`.
Сохраните формат из ответа, не переименовывайте PNG в WebP без реальной конвертации.
В случае сбоя отдельного файла повторяйте скачивание в пределах срока; ACK до
полного сохранения запрещён. После `404` перечитайте состояние задания.

## Подтверждение получения

`POST /v1/jobs/{job_id}/results/ack` без тела:

| Условие | Ответ |
| --- | --- |
| `AVAILABLE` до срока | `204`, доставка становится `ACKNOWLEDGED` |
| уже `ACKNOWLEDGED` | `204` |
| `EXPIRED` | `409 RESULTS_EXPIRED` |
| задание ещё не `COMPLETED` | `409 INVALID_JOB_STATE` |

## Отмена

`POST /v1/jobs/{job_id}/cancel` без тела возвращает представление задания
с `status=CANCELLED`. Отменить можно `QUEUED` или `PROCESSING`.
Повтор для `CANCELLED` успешен; для `COMPLETED` и `FAILED` — `409 INVALID_JOB_STATE`.
При гонке с завершением перечитайте GET и обработайте фактическое конечное состояние.

Все HTTP-ошибки операций описаны в [ERRORS.md](ERRORS.md).
