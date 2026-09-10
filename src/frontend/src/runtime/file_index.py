"""Keep Caspian's generated file inventory in sync with the checkout."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def refresh_file_index(project_root: Path) -> None:
    files = [
        f"./{path.relative_to(project_root).as_posix()}"
        for directory in ("src/app", "public")
        for path in sorted((project_root / directory).rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]
    index_path = project_root / "settings" / "files-list.json"
    try:
        if json.loads(index_path.read_text(encoding="utf-8")) == files:
            return
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=index_path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        json.dump(files, temporary, indent=2)
        temporary.write("\n")
    try:
        os.replace(temporary_path, index_path)
    finally:
        temporary_path.unlink(missing_ok=True)
