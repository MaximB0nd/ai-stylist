"""Copy the frontend into a standalone release directory with its source SHA."""

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        parser.error("каталог поставки должен быть вне исходного кода")
    commit = subprocess.check_output(
        ["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if destination.exists():
        parser.error("каталог поставки уже существует")
    shutil.copytree(
        ROOT, destination,
        ignore=shutil.ignore_patterns(
            ".venv", "node_modules", "__pycache__", "*.pyc", ".env",
            ".runtime", ".bootstrap", "dist", "build", ".casp", "caches",
        ),
    )
    (destination / ".source-revision").write_text(commit + "\n", encoding="ascii")
    print(f"release={destination} revision={commit}")


if __name__ == "__main__":
    main()
