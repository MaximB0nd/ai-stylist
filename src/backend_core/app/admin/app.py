"""Backend-only admin shell with read-only FastAdmin tables."""
import asyncio
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from html import escape
import json
import time
import uuid

import jwt
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.repositories.admin_repository import AdminRepository
from app.services import admin_service
from app.services.admin_monitoring_service import get_snapshot


def configure():
    # Set FastAdmin's singleton before importing its app or registering models.
    from fastadmin.settings import settings as config
    import os
    os.environ["ADMIN_PREFIX"] = "admin/data"
    config.ADMIN_PREFIX = "admin/data"
    config.ADMIN_USER_MODEL = "User"
    config.ADMIN_USER_MODEL_USERNAME_FIELD = "email"
    config.ADMIN_SECRET_KEY = settings.ADMIN_SECRET_KEY
    config.ADMIN_SITE_NAME = "AI Stylist — данные"
    config.ADMIN_LANGUAGE = "ru"
    config.ADMIN_SITE_SIGN_IN_LOGO = "/admin/data/static/images/sign-in-logo.svg"
    config.ADMIN_SITE_HEADER_LOGO = "/admin/data/static/images/header-logo.svg"
    config.ADMIN_SITE_FAVICON = "/admin/data/static/images/favicon.png"
    config.ADMIN_SESSION_ID_KEY = "stylist_admin_session"
    config.ADMIN_SESSION_EXPIRED_AT = 3600
    config.ADMIN_SESSION_COOKIE_SECURE = settings.ADMIN_COOKIE_SECURE
    config.ADMIN_SESSION_COOKIE_SAMESITE = "strict"
    config.ADMIN_QUERY_MAX_LIMIT = 100
    from app.admin import models  # noqa: F401
    from fastadmin import fastapi_app
    return fastapi_app


async def administrator(request):
    token = request.cookies.get("stylist_admin_session")
    if not token: return False
    try:
        data = jwt.decode(token, settings.ADMIN_SECRET_KEY, algorithms=["HS256"])
        expiry = datetime.fromisoformat(data["session_expired_at"])
        if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc): return False
        user_id = uuid.UUID(str(data["user_id"]))
    except (jwt.PyJWTError, ValueError, TypeError, KeyError): return False
    async with AsyncSessionLocal() as session:
        return await AdminRepository(session).is_admin(user_id)


def shell(title, content, refresh=False):
    links = (("overview", "Обзор"), ("generations", "Генерации"), ("users", "Пользователи"), ("albums", "Альбомы"), ("services", "Состояние сервисов"))
    nav = " | ".join(f'<a href="/admin/{path}">{label}</a>' for path, label in links)
    return HTMLResponse(f"""<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    {'<meta http-equiv="refresh" content="10">' if refresh else ''}<title>{escape(title)}</title>
    <style>body{{font:16px system-ui;margin:24px;color:#223}}nav{{margin-bottom:24px}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}table{{border-collapse:collapse}}iframe{{width:100%;height:82vh;border:0}}img{{max-width:260px;margin:8px}}pre{{white-space:pre-wrap}}</style>
    <nav>{nav} <form action="/admin/logout" method="post" style="display:inline"><button>Выйти</button></form></nav><h1>{escape(title)}</h1>{content}</html>""")



def services_table():
    data = get_snapshot()
    queue = data["delivery_queue"]
    state = lambda key: {"ok": "Работает", "unavailable": "Недоступен"}.get(data["checks"].get(key), "Ещё не проверено")
    pairs = [("PostgreSQL", state("postgresql")), ("MinIO / бакет", state("minio")),
             ("Последнее измерение (UTC)", data["sampled_at"] or "Ожидание первого измерения"),
             ("PID процесса", data.get("pid", "—")), ("CPU процесса, % (100% = одно ядро)", data.get("cpu_percent", "—")),
             ("RAM процесса, МБ", data.get("memory_mb", "—")), ("Время работы процесса, сек.", data.get("uptime_seconds", "—")),
             ("Очередь скачивания: ожидают / лимит", f'{queue["waiting"]} / {queue["capacity"]}'),
             ("Занятые обработчики скачивания / лимит", f'{queue["active_workers"]} / {queue["worker_limit"]}')]
    ai = data.get("ai")
    if ai:
        pairs.extend([("AI Core: последняя операция", ai["operation"]), ("Время обращения (UTC)", ai["at"]),
                      ("Длительность обращения, мс", ai["duration_ms"]), ("HTTP / ошибка", ai["http_status"] or ai["error"]),
                      ("Свежесть данных AI", "Устарели (>60 сек.)" if ai["stale"] else "Свежее наблюдение, не общая проверка готовности")])
    else: pairs.append(("AI Core", "Нет данных: обращений ещё не было"))
    return '<p>Измерения относятся к одному процессу backend, обновляются раз в 10 секунд.</p><table>' + ''.join(f'<tr><th>{escape(label)}</th><td>{escape(str(value))}</td></tr>' for label, value in pairs) + '</table>'


def create_admin_app():
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    signins = OrderedDict()

    @app.middleware("http")
    async def guard(request, call_next):
        path = request.url.path
        # Mounted apps may retain the parent prefix in ASGI scope.
        relative = path.removeprefix("/admin")
        signin = relative == "/data/api/sign-in"
        public = relative in ("/login", "/logout") or relative.startswith("/data/static/") or relative in ("/data", "/data/") or signin
        if signin:
            now = time.monotonic()
            address = request.client.host if request.client else "unknown"
            attempts = [t for t in signins.pop(address, []) if now - t < 60]
            signins[address] = attempts
            while len(signins) > 1024: signins.popitem(last=False)
            if len(attempts) >= 10: return JSONResponse({"detail": "Too many login attempts"}, status_code=429)
            attempts.append(now)
        if not public:
            try:
                allowed = await asyncio.wait_for(administrator(request), timeout=5)
            except Exception:
                return JSONResponse({"detail": "Admin authentication unavailable"}, status_code=503)
            if not allowed:
                if "/api/" in relative: return JSONResponse({"detail": "Administrator login required"}, status_code=401)
                return RedirectResponse("/admin/login", status_code=303)
        if request.method not in ("GET", "HEAD", "OPTIONS") and relative not in ("/data/api/sign-in", "/data/api/sign-out", "/logout"):
            return JSONResponse({"detail": "Read-only administration"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/login", response_class=HTMLResponse)
    async def login():
        return shell("Вход администратора", """<form id="login"><label>Email <input name="username" type="email" required autocomplete="username"></label>
        <label>Пароль <input name="password" type="password" required autocomplete="current-password"></label><button>Войти</button></form><p id="status" role="status"></p>
        <script>document.querySelector('#login').onsubmit=async e=>{e.preventDefault();const f=e.target;const button=f.querySelector('button');button.disabled=true;try{const r=await fetch('/admin/data/api/sign-in',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:f.username.value,password:f.password.value})});if(!r.ok)throw Error('Вход не выполнен: '+r.status);location.assign('/admin/overview');}catch(error){document.querySelector('#status').textContent=error.message;}finally{button.disabled=false;}};</script>""")

    @app.post("/logout")
    async def logout():
        response = RedirectResponse("/admin/login", status_code=303)
        response.delete_cookie("stylist_admin_session", path="/")
        return response

    @app.get("/")
    async def index(): return RedirectResponse("/admin/overview")

    @app.get("/overview")
    async def overview():
        try:
            data = await asyncio.wait_for(admin_service.overview(), timeout=5)
        except Exception:
            return shell("Обзор", "<p>Данные PostgreSQL сейчас недоступны. Повторная проверка через 10 секунд.</p>" + services_table(), refresh=True)
        active = {s: n for s, n in data["counts"].items() if s not in ("COMPLETED", "FAILED")}
        text = f'<p>Активных генераций: {sum(active.values())}</p><pre>{escape(json.dumps(active, ensure_ascii=False))}</pre>'
        text += f'<p>Завершено за 24 ч.: {data["recent"].get("COMPLETED", 0)}; ошибок: {data["recent"].get("FAILED", 0)}</p>'
        if data["oldest"]:
            row = data["oldest"]
            text += f'<p>Самая долгая: <a href="/admin/task/{row.id}">{row.generation_id}</a> — {escape(admin_service.duration(row))}</p>'
        text += '<h2>Последние задачи с ошибками</h2><ul>'
        for row in data["errors"]:
            text += f'<li><a href="/admin/task/{row.id}">{row.generation_id}</a>: {escape(admin_service.safe_error(row.error_message))}</li>'
        text += '</ul><p>Старые задачи без времени завершения не входят в статистику за 24 часа.</p><h2>Состояние backend</h2>' + services_table()
        return shell("Обзор", text, refresh=True)

    @app.get("/generations")
    async def generations(request: Request):
        from urllib.parse import urlencode
        status = request.query_params.get("status", "")[:20]
        search = request.query_params.get("search", "")[:64]
        try: offset = max(0, min(100000, int(request.query_params.get("offset", 0))))
        except ValueError: offset = 0
        from_date = request.query_params.get("from_date", "")
        to_date = request.query_params.get("to_date", "")
        try:
            since = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) if from_date else None
            until = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1) if to_date else None
        except ValueError: raise HTTPException(400, "Invalid date")
        rows, count = await asyncio.wait_for(admin_service.generations(status or None, search or None, offset, since, until), timeout=5)
        text = '<form><label>Статус <select name="status"><option value="">Все</option>'
        for value in ("VALIDATING", "QUEUED", "PROCESSING", "DOWNLOADING", "COMPLETED", "FAILED"):
            text += f'<option {"selected" if value == status else ""}>{value}</option>'
        text += f'</select></label> <label>С <input type="date" name="from_date" value="{escape(from_date, quote=True)}"></label> <label>По <input type="date" name="to_date" value="{escape(to_date, quote=True)}"></label> <label>ID генерации / AI Core <input name="search" value="{escape(search, quote=True)}"></label> <button>Найти</button></form><p>Всего: {count}</p><table><tr><th>ID</th><th>AI ID</th><th>Статус</th><th>Создана (UTC)</th><th>Длительность</th><th>Последнее изменение</th><th>Ошибка</th></tr>'
        for row in rows:
            text += f'<tr><td><a href="/admin/task/{row.id}">{row.generation_id}</a></td><td>{row.ai_job_id or "—"}</td><td>{escape(row.status)}</td><td>{row.created_at}</td><td>{admin_service.duration(row)}</td><td>{row.updated_at}</td><td>{escape(admin_service.safe_error(row.error_message))}</td></tr>'
        text += '</table>'
        for label, page in (("Назад", offset - 25), ("Далее", offset + 25)):
            if 0 <= page < count:
                url = urlencode({"status": status, "search": search, "offset": page, "from_date": from_date, "to_date": to_date})
                text += f' <a href="/admin/generations?{escape(url, quote=True)}">{label}</a>'
        return shell("Генерации", text, refresh=not search and not status)

    @app.get("/services")
    async def services():
        return shell("Состояние сервисов", services_table(), refresh=True)

    @app.get("/api/snapshot")
    async def snapshot(): return get_snapshot()

    @app.get("/user/{user_id}")
    async def user_details(user_id: uuid.UUID):
        data = await admin_service.user_details(user_id)
        if data is None: raise HTTPException(404, "User not found")
        profile, tasks = data
        text = '<table>' + ''.join(f'<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>' for k, v in profile.items()) + '</table><h2>Последние 25 генераций / альбомов</h2><ul>'
        for row in tasks:
            text += f'<li><a href="/admin/task/{row.id}">{row.generation_id}</a> — {escape(row.title)} — {escape(row.status)}</li>'
        return shell("Пользователь", text + '</ul>')

    @app.get("/task/{album_id}")
    async def task(album_id: uuid.UUID):
        data = await admin_service.task(album_id)
        if data is None: raise HTTPException(404, "Generation not found")
        photos = data.pop("photos")
        user_id = data["user_id"]
        text = f'<p><a href="/admin/user/{user_id}">Пользователь</a> | <a href="/admin/data/#/change/Album/{album_id}">Альбом</a></p><table>'
        for key, value in data.items(): text += f'<tr><th>{escape(key)}</th><td>{escape(str(value))}</td></tr>'
        text += '</table><h2>Сохранённые фотографии</h2>'
        for url in photos:
            if url.startswith(("http://", "https://")):
                text += f'<a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer"><img src="{escape(url, quote=True)}" alt="Готовый образ"></a>'
        return shell("Генерация", text)

    for route, label, model in (("users", "Пользователи", "User"), ("albums", "Альбомы", "Album")):
        def make_view(label, model):
            def view():
                return shell(label, f'<iframe title="{label}" src="/admin/data/#/list/{model}"></iframe>')
            return view
        app.add_api_route('/' + route, make_view(label, model), methods=["GET"])
    app.mount("/data", configure())
    return app
