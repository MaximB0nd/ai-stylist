from src.runtime.caspian_app import app
from src.runtime.server import run_dev_server

__all__ = ["app"]


if __name__ == "__main__":
    run_dev_server()
