from pathlib import Path

from src.runtime.file_index import refresh_file_index
from src.runtime.server import run_dev_server

__all__ = ["app"]


def _load_app():
    # Refresh generated routes before Caspian caches their index.
    refresh_file_index(Path(__file__).resolve().parent)
    from src.runtime.caspian_app import app

    return app


app = _load_app()


if __name__ == "__main__":
    run_dev_server()
