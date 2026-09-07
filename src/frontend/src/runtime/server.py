import os
import secrets
import sys
import threading
from typing import Any

import uvicorn


def _consume_dev_control_stream(
    server: uvicorn.Server,
    expected_token: str,
    stream: Any,
) -> None:
    """Watch the private parent-process pipe for a graceful shutdown request."""
    for raw_line in stream:
        command, separator, token = raw_line.rstrip("\r\n").partition(":")
        if separator and command == "shutdown" and secrets.compare_digest(token, expected_token):
            server.should_exit = True
            return

    server.should_exit = True


def _start_dev_control_listener(
    server: uvicorn.Server,
    expected_token: str,
) -> threading.Thread:
    listener = threading.Thread(
        target=_consume_dev_control_stream,
        args=(server, expected_token, sys.stdin),
        name="caspian-dev-control",
        daemon=True,
    )
    listener.start()
    return listener


def run_dev_server() -> None:
    port = int(os.getenv("PORT", 5091))
    workers = max(1, int(os.getenv("UVICORN_WORKERS", "1")))
    dev_control_token = os.getenv("CASPIAN_DEV_CONTROL_TOKEN", "")

    if dev_control_token:
        server = uvicorn.Server(
            uvicorn.Config(
                "main:app",
                host="0.0.0.0",
                port=port,
                reload=False,
                workers=1,
            )
        )
        _start_dev_control_listener(server, dev_control_token)
        server.run()
        return

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        workers=workers,
    )
