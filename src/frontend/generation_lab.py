"""Reproducible, offline readiness check for the generation page."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from src.pages.generation import page


ROOT = Path(__file__).resolve().parent
MODES = {"basic", "full"}


def revision() -> str:
    saved = ROOT / ".source-revision"
    if saved.is_file():
        return saved.read_text(encoding="ascii").strip()
    result = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return "unknown"
    sha = result.stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "src/frontend"],
        cwd=ROOT.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    return sha + ("+dirty" if dirty.stdout.strip() else "")


def check_generation(mode: str) -> dict:
    if mode not in MODES:
        raise ValueError("GENERATION_LAB_MODE должен быть basic или full")
    soup = BeautifulSoup(str(page()), "html.parser")
    form = soup.select_one("#generation-form")
    if form is None:
        raise RuntimeError("Не найдена форма генерации")
    fields = form.select('input[type="number"]')
    photos = form.select('input[type="file"]')
    questions = form.select("[data-question]")
    if len(fields) != 2 or len(photos) != 2 or len(questions) != 4:
        raise RuntimeError("Структура формы генерации не соответствует контракту")
    if mode == "full":
        for field in fields:
            if not all(field.has_attr(key) for key in ("min", "max", "step", "required")):
                raise RuntimeError(f"Нет ограничений поля {field.get('name', '?')}")
        for photo in photos:
            if photo.get("accept") != "image/jpeg,image/png,image/webp":
                raise RuntimeError(f"Неверный формат фото {photo.get('name', '?')}")
        for image in soup.select(".generation-page img[src]"):
            source = urlsplit(image["src"]).path
            if not source.startswith("/images/generation/"):
                raise RuntimeError(f"Неожиданный ресурс {source}")
            if not (ROOT / "public" / source.lstrip("/")).is_file():
                raise RuntimeError(f"Отсутствует ресурс {source}")
    return {"status": "ok", "mode": mode, "numeric_fields": len(fields),
            "photo_fields": len(photos), "questions": len(questions)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="store_true", help="показать версию и состояние исходного кода")
    parser.add_argument("--check", action="store_true", help="проверить страницу генерации")
    args = parser.parse_args()
    version = f"{os.getenv('GENERATION_LAB_VERSION', '1.0.0')}+{revision()}"
    if args.version:
        print(version)
        return 0
    if not args.check:
        parser.error("укажите --version или --check")
    mode = os.getenv("GENERATION_LAB_MODE", "full")
    print(json.dumps({"event": "generation_check_started", "version": version,
                      "mode": mode}, ensure_ascii=False), file=sys.stderr)
    try:
        result = check_generation(mode)
    except (ValueError, RuntimeError) as error:
        print(json.dumps({"event": "generation_check_failed", "reason": str(error)},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"event": "generation_check_completed", **result},
                     ensure_ascii=False), file=sys.stderr)
    print(json.dumps({"version": version, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
