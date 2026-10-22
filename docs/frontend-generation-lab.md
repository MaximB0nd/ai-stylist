# Практическая работа № 1: страница генерации

Автор: Валаева Ирина Владимировна. Компонент: `src/frontend/generation_lab.py`.

## Инструментальный контур

| Позиция | Средство и назначение | Подключение | Статус |
|---|---|---|---|
| Подготовка к исполнению | `uv sync --frozen` устанавливает Python и зависимости; `package_generation_lab.py` готовит каталог поставки | `src/frontend/pyproject.toml`, `uv.lock`, `scripts/package_generation_lab.py` | Работает |
| Зависимости | uv lock фиксирует прямые и транзитивные версии Python-пакетов; npm lock фиксирует JS tooling | `uv.lock`, `package-lock.json` | Работает |
| Тестирование | `unittest` проверяет штатный и ошибочный исход; Node test runner проверяет JS-валидацию формы | `tests/test_generation_lab.py`, `tests/generation_validation.test.js` | Работает |
| Статический анализ | `python -m compileall` проверяет синтаксис Python, `node --check` — синтаксис JS | Локальная команда, ниже | Работает для синтаксиса; расширенный анализ запланирован |
| Динамическая диагностика | JSON-события в stderr; `pdb` для пошаговой отладки Python | `python -m pdb generation_lab.py --check` | Диагностика работает; отладчик доступен |
| Профилирование | `cProfile` измеряет время вызовов проверки | `python -m cProfile -s cumulative generation_lab.py --check` | Средство определено; измерение не входит в оценку этой работы |
| Автоматические проверки | GitHub Actions запускает тест и проверяет, что неверная конфигурация завершится ошибкой | `.github/workflows/frontend-generation-lab.yml` | Настроено; результат удалённого запуска подтверждается ссылкой после PR |

## Чистый запуск

Требуются Git, uv и доступ к зависимостям, объявленным в `uv.lock`. Команды из корня клона:

```sh
cd src/frontend
uv sync --frozen
uv run python generation_lab.py --version
GENERATION_LAB_MODE=full uv run python generation_lab.py --check
GENERATION_LAB_MODE=invalid uv run python generation_lab.py --check
uv run python -m unittest tests.test_generation_lab -v
```

Последняя команда с `invalid` намеренно завершится кодом 2. `basic` проверяет число полей, `full` также проверяет ограничения полей и наличие иллюстраций. В stdout выводится итог в JSON, в stderr — события старта и завершения/ошибки. Секреты не читаются и не выводятся. Повторный запуск не меняет исходные файлы и не требует восстановления данных.

## Путь исполнения

`generation_lab.py` и Python-модули страницы → `uv sync --frozen` → импорт модулей и компиляция Python в байт-код при загрузке → Python 3.14 выполняет `page()` → BeautifulSoup проверяет HTML и локальные файлы → JSON-результат и код завершения. Состав байт-кода можно посмотреть командой `uv run python -m dis generation_lab.py`; состав зависимостей — `uv tree --depth 1`.

## Режимы

Разработка: команда `uv run python generation_lab.py --check` из исходного дерева, SHA берётся из Git и получает `+dirty` при несохранённых изменениях. Поставка: `python scripts/package_generation_lab.py /tmp/generation-lab-release`, затем из этого каталога `uv sync --frozen` и `uv run python generation_lab.py --check`; SHA хранится в `.source-revision`, исходный `.git` не нужен. В обоих режимах сохраняются проверки и диагностические события. Отличие — состав каталога и источник идентификатора версии. Ускорение исполнения не заявляется.

Чтобы повторить поставку, удалите прежний каталог `/tmp/generation-lab-release` и выполните упаковку заново. Каталог должен находиться вне исходного репозитория.

## Независимая проверка

Другой студент должен выполнить команды раздела «Чистый запуск» на чистой машине или в отдельном контейнере, записать дату, ОС, версии uv/Python, commit, команды, фактический результат и замечания. Авторская проверка не заменяет этот протокол. Если обнаружена скрытая зависимость, её следует устранить и повторить проверку с исходного чистого состояния.
