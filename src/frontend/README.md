# AI Stylist Frontend

Минимальный запускаемый frontend-каркас AI Stylist на Caspian.

## Структура

```text
src/frontend/
  main.py                 точка входа Caspian/FastAPI приложения
  caspian.config.json     настройки проекта Caspian
  package.json            npm-скрипты для Caspian tooling
  pyproject.toml          Python-зависимости
  public/
    css/                  стили для браузера
      base.css            глобальные базовые стили
      pages/              стили отдельных страниц
    js/                   браузерный bootstrap-код
      vendor/             сторонние или framework runtime файлы
  settings/               build-скрипты Caspian и generated indexes
  src/
    app/                  route adapters для Caspian; имена route-файлов держим здесь
    layouts/              общие layout-файлы страниц
    pages/                реализация страниц
    runtime/              сборка Caspian/FastAPI app и запуск сервера
    shared/               общие Python-модули приложения
```

`src/app` намеренно тонкий: Caspian находит routes по файлам в этой папке,
а реальный код страниц лежит в `src/pages` и `src/layouts`.
`main.py` — только Python-точка входа; детали runtime лежат в `src/runtime`.

Для обычной frontend-разработки начинай с `src/pages`, `src/layouts`,
`src/shared` и `public/css`. Папки `src/runtime` и `settings` считаются
инфраструктурой; трогай их только если нужно менять саму связку фреймворка.

## Требования

- Node.js 24 или новее
- uv

Python 3.14 и все Python-пакеты устанавливаются автоматически через uv.

## Первый запуск

```powershell
cd src/frontend
npm install
uv sync
npm run dev
```

Открой frontend URL, который появится в терминале. Адрес по умолчанию:
`http://localhost:5091`.

Frontend самодостаточен внутри этой папки и не требует запущенного backend.

## После обновления из Git

Останови запущенный сервер через `Ctrl+C`. Из папки `src/frontend` выполни:

```powershell
npm install
uv sync
npm run dev
```

`npm run dev` пересобирает служебные файлы и запускает сервер.
При запуске через `main.py` список маршрутов также автоматически сверяется
с файлами проекта. После обновления всё равно перезапусти сервер:
уже работающий процесс не подхватывает новые маршруты.
Сам по себе `npm run build` подготавливает файлы, но не запускает сервер.

Главная открывается по `http://localhost:5091/`, страница генерации — по
`http://localhost:5091/generation`. Перейти к ней можно кнопкой «Генерировать»
на главной или пунктом «Генерация» в боковом меню.
