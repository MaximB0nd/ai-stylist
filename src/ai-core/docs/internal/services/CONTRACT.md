# Общий договор processing services

## Область действия

Этот договор обязателен для независимо разворачиваемых служб обработки AI Core:
проверок, нормализации, классификации, стилизации и генерации. Главный
оркестратор, внешний API и служба временных файлов имеют собственные договоры.

Общие границы ответственности, безопасность файлов, правила повторов, жизненный
цикл моделей и наблюдаемость описаны в [README.md](README.md). Этот документ
фиксирует только общий HTTP-интерфейс processing services.

Перед реализацией каждая служба дополняет этот документ собственным
`CONTRACT.md`: фиксирует endpoint, поля запроса, варианты успешного ответа и
стабильные причины отрицательного решения. В этой итерации такие договоры
зафиксированы для служб подготовки и нормализации фотографий. При расхождении
действует более узкий договор службы, если он не отменяет требования
безопасности и независимости из этого документа.

## Транспорт

| Правило | Значение |
| --- | --- |
| Сеть | внутренняя, HTTPS |
| Формат метаданных | `application/json` |
| Авторизация рабочего endpoint | `Authorization: Bearer <service-token>` |
| Корреляция | `request_id`, UUID |
| Файлы | короткие `read_url` и `write_url` доверенной службы файлов, не байты в JSON |
| Состояние задания | не передаётся |

`request_id` связывает журналы и ответ с вызовом, но не несёт смысла задания.
Служба возвращает его без изменения. Ссылки, токены и содержимое изображений
запрещено журналировать.

`read_url` и `write_url` являются короткоживущими capability URLs и используются
только вместе с `Authorization: Bearer <artifact-client-token>`. Этот токен
берётся из локальной конфигурации службы, не передаётся в теле запроса и не
включается в URL. Bearer-токен рабочего endpoint processing service не даёт
доступа к artifact service и не переиспользуется как artifact-client token.

Пример входного файла:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "image": {
    "read_url": "https://temporary-files.example/opaque-read-token",
    "checksum_sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }
}
```

`checksum_sha256` имеет формат `sha256:<64 lowercase hex characters>`.
Неизвестные поля запроса отклоняются с `422 VALIDATION_ERROR`, чтобы опечатка не
меняла смысл вызова незаметно для клиента.

Для файлового результата вызывающая сторона заранее передаёт `write_url`.
Служба не получает адрес S3 или ключи доступа и не сохраняет файл локально
дольше одного вызова.

## Решения предметной области

HTTP `200` означает, что служба выполнила обещанную операцию и вернула результат.
Для службы, задача которой — проверить пригодность изображения, отрицательное
решение является таким результатом:

```json
{
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "decision": "REJECTED",
  "reasons": ["FACE_TOO_BLURRY"],
  "model_version": "model@revision"
}
```

Такое решение возвращается с HTTP `200`, потому что проверка успешно завершена.
Массив `reasons` содержит уникальные коды без гарантированного порядка; клиент
проверяет наличие кода, а не позицию. Если служба обещает создать артефакт,
сравнить входы или вернуть классификацию, отсутствие этого результата не
является успешным ответом и оформляется подходящим `4xx` или `5xx`.

Служба не возвращает внутренние score, confidence, признаки или пороги, если её
собственный договор явно не требует обратного.

## Ошибки

Ошибки используют `Content-Type: application/problem+json` и формат Problem
Details. Поля `code`, `request_id` и `retryable` являются расширениями общего
формата:

```json
{
  "type": "urn:ai-core:problem:input-unavailable",
  "title": "Input is unavailable",
  "status": 502,
  "detail": "The image could not be read from the provided URL.",
  "instance": "urn:uuid:4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "code": "INPUT_UNAVAILABLE",
  "request_id": "4bb167f7-cfeb-4c4c-b4ba-c63e64e96adb",
  "retryable": true
}
```

`type`, `title`, `status`, `code` и `retryable` обязательны. `detail` содержит
только безопасное объяснение без stack trace, пути к файлам и ответа зависимости.
`instance` и `request_id` обязательны, когда служба смогла прочитать корректный
`request_id`; для ошибки структуры самого запроса они могут отсутствовать.
`VALIDATION_ERROR` дополнительно содержит массив `errors` с безопасными полями
`pointer`, `code` и `detail` для каждого неверного поля запроса.

| HTTP | `code` | Условие | `retryable` |
| ---: | --- | --- | --- |
| `400` | `MALFORMED_REQUEST` | HTTP-тело нельзя разобрать как JSON | нет |
| `401` | `UNAUTHORIZED` | неверный служебный токен | нет |
| `409` | `CHECKSUM_MISMATCH` | checksum входа не совпал | нет |
| `409` | `OUTPUT_CONFLICT` | место записи занято другим логическим результатом | нет |
| `413` | `REQUEST_TOO_LARGE` | HTTP-тело запроса превышает предел | нет |
| `415` | `UNSUPPORTED_REQUEST_MEDIA_TYPE` | HTTP-тело запроса не `application/json` | нет |
| `422` | `ARTIFACT_URL_NOT_ALLOWED` | ссылка направлена не на разрешённую службу файлов | нет |
| `422` | `INPUT_TOO_LARGE` | файл по `read_url` превышает предел байтов | нет |
| `422` | `IMAGE_DIMENSIONS_EXCEEDED` | размеры, число пикселей или кадров превышают предел | нет |
| `422` | `VALIDATION_ERROR` | корректный JSON не соответствует схеме запроса | нет |
| `422` | `UNSUPPORTED_IMAGE_TYPE` | файл по `read_url` имеет неподдерживаемый формат | нет |
| `422` | `INPUT_UNPROCESSABLE` | изображение нельзя декодировать или обработать | нет |
| `429` | `CAPACITY_EXCEEDED` | достигнут локальный предел вызовов | да |
| `500` | `INFERENCE_FAILED` | выполнение модели завершилось неожиданной ошибкой | нет |
| `502` | `INPUT_ACCESS_EXPIRED` | истекла короткая ссылка чтения | да, с новой ссылкой |
| `502` | `OUTPUT_ACCESS_EXPIRED` | истекла короткая ссылка записи | да, с новой ссылкой и новым выходом |
| `502` | `INPUT_UNAVAILABLE` | чтение отклонено или файловая служба временно недоступна | зависит от причины |
| `502` | `OUTPUT_UNAVAILABLE` | запись отклонена или файловая служба временно недоступна | зависит от причины |
| `503` | `MODEL_UNAVAILABLE` | модель или обязательная зависимость не готовы | да |
| `504` | `INPUT_TIMEOUT` | файловая служба не ответила вовремя при чтении | да |
| `504` | `OUTPUT_TIMEOUT` | файловая служба не ответила вовремя при записи | да |

Договор конкретной службы может добавлять более точные коды `422`. Ответ `401`
содержит `WWW-Authenticate: Bearer`; ответы `429` и `503` содержат
`Retry-After`. Только вызывающая сторона решает, выполнять ли повтор ошибки с
`retryable: true`.

При ответе artifact gateway processing service отображает причины следующим
образом; исходный статус и тело gateway не передаются клиенту:

| Ответ gateway | Ответ processing service | `retryable` |
| --- | --- | --- |
| `410` для истёкшей capability-ссылки | `502 INPUT_ACCESS_EXPIRED` или `OUTPUT_ACCESS_EXPIRED` | `true` |
| `429`, `5xx`, ошибка соединения | `502 INPUT_UNAVAILABLE` или `OUTPUT_UNAVAILABLE` | `true` |
| `401`, `403`, `404`, `405`, `413`, `415`, `400`, `422` | `502 INPUT_UNAVAILABLE` или `OUTPUT_UNAVAILABLE` | `false` |
| `409` при записи в уже занятый или закрытый выход | `409 OUTPUT_CONFLICT` | `false` |

Прочие постоянные ответы gateway также дают `INPUT_UNAVAILABLE` или
`OUTPUT_UNAVAILABLE` с `retryable: false`. `410` требует нового URL от
вызывающей стороны: повтор того же HTTP-запроса с истёкшей ссылкой запрещён.
Повтор после принятой попытки записи получает новый output `artifact_id`; новую
ссылку для него выдаёт оркестратор. Ошибки авторизации gateway не исправляются
обновлением capability-ссылки.

## Служебные endpoints

```text
GET /health/live
GET /health/ready
GET /health/status
```

- `live` возвращает `200`, пока HTTP-процесс способен отвечать. Он не проверяет
  модель, зависимости или свободную capacity.
- `ready` возвращает `200`, когда модели и обязательные зависимости загружены и
  экземпляр не находится в `STARTING`, `DRAINING` или `UNAVAILABLE`.
  `SATURATED` остаётся технически ready: отсутствие свободного слота выражается
  через status и атомарный `429` рабочего endpoint.
- `status` возвращает моментальный статус конкретного экземпляра. Endpoint не
  запускает inference, не обращается к входным файлам и не выполняет тяжёлую
  проверку зависимости на каждый запрос.

HTTP `200` от `GET /health/status`:

```json
{
  "service": "face-validation",
  "instance_id": "01K6F7M4B8D2N5Q9R3T1V0WXYZ",
  "state": "BUSY",
  "accepting_requests": true,
  "in_flight": 1,
  "concurrency_limit": 2,
  "available_capacity": 1,
  "model_ready": true
}
```

`instance_id` — непрозрачный идентификатор запуска процесса. Он меняется после
перезапуска, не содержит hostname или адрес и не является состоянием задания.

| `state` | Значение | `accepting_requests` |
| --- | --- | --- |
| `STARTING` | процесс запущен, модель или зависимости ещё загружаются | `false` |
| `IDLE` | экземпляр готов, активных рабочих вызовов нет | `true` |
| `BUSY` | часть локальной capacity занята, свободный слот ещё есть | `true` |
| `SATURATED` | все локальные слоты заняты | `false` |
| `DRAINING` | экземпляр завершает принятые вызовы перед остановкой | `false` |
| `UNAVAILABLE` | HTTP-процесс жив, но модель или обязательная зависимость неисправна | `false` |

Инварианты capacity:

- `concurrency_limit` — положительный локальный предел рабочих вызовов;
- `in_flight` — число уже принятых и ещё не завершённых рабочих вызовов;
- `available_capacity = max(concurrency_limit - in_flight, 0)`;
- `IDLE` требует `in_flight = 0`, `BUSY` — значения между нулём и пределом,
  `SATURATED` — отсутствие свободной capacity;
- переход в `DRAINING` немедленно запрещает новые вызовы, но не отменяет уже
  принятые.

Status является advisory snapshot, а не резервированием слота. Между чтением
`IDLE` или `BUSY` и рабочим запросом другой клиент может занять последнюю
capacity. Рабочий endpoint атомарно увеличивает `in_flight` до начала чтения
файлов или inference; если слота нет, он возвращает `429 CAPACITY_EXCEEDED` с
`Retry-After`. Вызывающая сторона обязана обрабатывать этот ответ независимо от
предыдущего status.

Упавший процесс не может вернуть собственное состояние. Timeout, connection
refused или отсутствие endpoint вызывающая сторона отображает как наблюдаемое
состояние `UNREACHABLE`; это не значение поля `state` в ответе службы. Health и
status не содержат `request_id` активных вызовов, данные задания, ссылки,
токены, model scores или другие секреты.

## Основания договора

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [RFC 6585: Additional HTTP Status Codes](https://www.rfc-editor.org/rfc/rfc6585.html)
- [OWASP: Server-Side Request Forgery Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
