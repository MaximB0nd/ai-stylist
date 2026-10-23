"""Small process-local monitoring snapshot; no payloads or signed URLs."""
import asyncio
import os
import time
from datetime import datetime, timezone

import psutil
from app.services.health_service import readiness

snapshot = {"sampled_at": None, "checks": {}, "ai": None}


def record_ai(operation, started, status=None, error=None):
    snapshot["ai"] = {
        "operation": operation, "at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
        "http_status": status, "error": error,
    }


class ObservedClient:
    def __init__(self, client):
        self.client = client

    def __getattr__(self, name):
        return getattr(self.client, name)

    async def _request(self, method, url, **kwargs):
        from app.core.config import settings
        if not settings.ADMIN_ENABLED:
            return await getattr(self.client, method)(url, **kwargs)
        operation = "ack" if str(url).endswith("/ack") else "cancel" if str(url).endswith("/cancel") else "poll" if method == "get" else "create"
        started = time.monotonic()
        try:
            result = await getattr(self.client, method)(url, **kwargs)
        except Exception as exc:
            record_ai(operation, started, error=type(exc).__name__)
            raise
        record_ai(operation, started, status=result.status_code)
        return result

    async def get(self, url, **kwargs):
        return await self._request("get", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._request("post", url, **kwargs)


async def monitoring_loop():
    process = psutil.Process()
    process.cpu_percent(None)
    while True:
        try:
            snapshot.update(
                sampled_at=datetime.now(timezone.utc).isoformat(),
                checks=await readiness(), pid=os.getpid(),
                cpu_percent=process.cpu_percent(None),
                memory_mb=round(process.memory_info().rss / 1024**2, 1),
                uptime_seconds=round(time.time() - process.create_time()),
            )
        except Exception:
            snapshot.update(sampled_at=datetime.now(timezone.utc).isoformat(), checks={"monitoring": "unavailable"})
        await asyncio.sleep(10)


def get_snapshot():
    from app.services.generation_queue import get_generation_queue
    from app.core.config import settings
    result = dict(snapshot)
    queue = get_generation_queue()
    result["delivery_queue"] = {"waiting": queue.queue.qsize(), "capacity": queue.queue.maxsize,
                                "active_workers": queue.active_workers, "worker_limit": settings.GENERATION_DOWNLOAD_WORKERS}
    if result["ai"]:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(result["ai"]["at"])).total_seconds()
        result["ai"] = {**result["ai"], "stale": age > 60}
    return result
