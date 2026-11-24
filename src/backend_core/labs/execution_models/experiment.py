import asyncio
import hashlib
import json
import os
import platform
import random
import statistics
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx
import psutil
from dotenv import load_dotenv
from PIL import Image
from fastapi import HTTPException

BASE = Path(__file__).resolve().parent
ROOT = next(p for p in BASE.parents if (p / "src/backend_core").is_dir())
load_dotenv(ROOT / "src/backend_core/.env.test")
sys.path.insert(0, str(ROOT / "src/backend_core"))
from app.services.image_service import normalize_png
from app.services.album_service import AlbumService


def normalize(data):
    return normalize_png(data)


def stats(values):
    med = statistics.median(values)
    return {
        "raw": values,
        "min": min(values),
        "median": med,
        "max": max(values),
        "spread": (max(values) - min(values)) / med,
    }


def cpu():
    data = []
    rng = random.Random(42)
    for _ in range(16):
        with (
            Image.frombytes("RGB", (512, 512), rng.randbytes(512 * 512 * 3)) as im,
            BytesIO() as out,
        ):
            im.save(out, format="JPEG", quality=85)
            data.append(out.getvalue())

    def sequential():
        return [normalize(x) for x in data]

    expected = sequential()
    print("CPU: prepared 16 JPEGs", flush=True)
    results = {}
    with (
        ProcessPoolExecutor(2) as p2,
        ProcessPoolExecutor(4) as p4,
        ProcessPoolExecutor(os.cpu_count()) as pn,
    ):
        variants = {"seq": sequential}
        for count, pool in [(2, p2), (4, p4), (os.cpu_count(), pn)]:
            variants[str(count)] = lambda pool=pool: list(
                pool.map(normalize, data, chunksize=1)
            )
        samples = {key: [] for key in variants}
        for run in range(7):
            for key, function in variants.items():
                start = time.perf_counter()
                output = function()
                elapsed = time.perf_counter() - start
                assert output == expected
                if run >= 2:
                    samples[key].append(elapsed)
        for key, vals in samples.items():
            results[key] = stats(vals)
    results["dataset_sha256"] = hashlib.sha256(b"".join(data)).hexdigest()
    return results


async def io_experiment():
    payload = b"x" * 32768

    async def serve(reader, writer):
        try:
            await reader.readuntil(b"\r\n\r\n")
            await asyncio.sleep(0.02)
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: 32768\r\nConnection: close\r\n\r\n"
                + payload
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server, httpx.AsyncClient(trust_env=False) as client:

        async def run(limit):
            sem = asyncio.Semaphore(limit)

            async def fetch():
                async with sem:
                    response = await client.get(f"http://127.0.0.1:{port}/")
                    response.raise_for_status()
                    return response.content

            if limit == 1:
                result = [await fetch() for _ in range(24)]
            else:
                result = await asyncio.gather(*(fetch() for _ in range(24)))
            assert result == [payload] * 24

        vals = {k: [] for k in (1, 2, 4, 8)}
        for round in range(7):
            for k in vals:
                start = time.perf_counter()
                await run(k)
                if round >= 2:
                    vals[k].append(time.perf_counter() - start)
    return {k: stats(v) for k, v in vals.items()}


async def summary(variant):
    counts = {}
    lock = asyncio.Lock()

    async def worker(worker_id):
        local = {}
        for i in range(64):
            album = i % 8
            if variant == "local":
                local[album] = local.get(album, 0) + 1
                await asyncio.sleep(0)
            elif variant == "lock":
                async with lock:
                    value = counts.get(album, 0)
                    await asyncio.sleep(0)
                    counts[album] = value + 1
            else:
                value = counts.get(album, 0)
                await asyncio.sleep(0)
                counts[album] = value + 1
        return local

    parts = await asyncio.gather(*(worker(i) for i in range(8)))
    if variant == "local":
        for part in parts:
            for key, count in part.items():
                counts[key] = counts.get(key, 0) + count
    return counts


async def race():
    failures = {}
    for variant in ("broken", "lock", "local"):
        bad = 0
        for _ in range(100):
            result = await summary(variant)
            bad += result != dict.fromkeys(range(8), 64)
        failures[variant] = bad
    assert failures["broken"] and failures["local"] == failures["lock"] == 0
    times = {key: [] for key in ("local", "lock")}
    for round in range(7):
        for key in times:
            start = time.perf_counter()
            for _ in range(20):
                assert await summary(key) == dict.fromkeys(range(8), 64)
            if round >= 2:
                times[key].append(time.perf_counter() - start)
    return {
        "failures_per_100": failures,
        "timing_20_batches": {k: stats(v) for k, v in times.items()},
    }


class Signer:
    def __init__(self, cached=None):
        self.cached = cached

    def presigned_url(self, key):
        if self.cached is not None:
            return self.cached[key]
        time.sleep(0.01)
        return "https://test.invalid/" + key


class BoundedAlbumService(AlbumService):
    async def get_album(self, album_id, current_user_id):
        album = await self.album_repo.get_by_id_with_photos(album_id)
        if album is None or album.user_id != current_user_id:
            return await super().get_album(album_id, current_user_id)
        keys = [p.object_key for p in album.photos]
        keys += [k for k in (album.source_face_key, album.source_body_key) if k]
        sem = asyncio.Semaphore(4)

        async def sign(key):
            async with sem:
                return key, await asyncio.to_thread(self.storage.presigned_url, key)

        cached = dict(await asyncio.gather(*(sign(k) for k in keys)))

        async def read(_):
            return album

        service = AlbumService(
            SimpleNamespace(get_by_id_with_photos=read), Signer(cached)
        )
        return await service.get_album(album_id, current_user_id)


async def album():
    owner = uuid.uuid4()
    row = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=owner,
        title="Test",
        situation="office",
        styles=["casual"],
        shoes=[],
        impressions=[],
        user_age=25,
        user_height=175,
        gender="m",
        source_face_key="face",
        source_body_key="body",
        created_at=datetime.now(timezone.utc),
        is_archived=False,
        total_photos=5,
        photos=[
            SimpleNamespace(id=uuid.uuid4(), order_index=i, object_key=str(i))
            for i in range(5)
        ],
    )

    async def read(key):
        return row if key == row.id else None

    repo = SimpleNamespace(get_by_id_with_photos=read)
    services = {
        "baseline": AlbumService(repo, Signer()),
        "bounded4": BoundedAlbumService(repo, Signer()),
    }
    expected = (await services["baseline"].get_album(row.id, owner)).model_dump()
    for service in services.values():
        for key, user, code in [
            (uuid.uuid4(), owner, 404),
            (row.id, uuid.uuid4(), 403),
        ]:
            try:
                await service.get_album(key, user)
            except HTTPException as exc:
                assert exc.status_code == code
            else:
                raise AssertionError()
        old = row.source_face_key, row.source_body_key
        row.source_face_key = row.source_body_key = None
        assert (await service.get_album(row.id, owner)).source_face_url is None
        row.source_face_key, row.source_body_key = old

        class Failing(Signer):
            def presigned_url(self, key):
                if key == "1":
                    raise TimeoutError("injected")
                return super().presigned_url(key)

        try:
            await type(service)(repo, Failing()).get_album(row.id, owner)
        except TimeoutError:
            pass
        else:
            raise AssertionError()
    samples = {key: [] for key in services}
    for round in range(7):
        for key, service in services.items():
            start = time.perf_counter()
            result = await service.get_album(row.id, owner)
            if round >= 2:
                samples[key].append(time.perf_counter() - start)
            assert result.model_dump() == expected
    return {key: stats(values) for key, values in samples.items()}


async def async_experiments():
    return {"io": await io_experiment(), "race": await race(), "album": await album()}


if __name__ == "__main__":
    results = {
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "physical": psutil.cpu_count(False),
            "logical": os.cpu_count(),
            "ram_gib": psutil.virtual_memory().total / 2**30,
        },
        "cpu": cpu(),
    }
    results.update(asyncio.run(async_experiments()))
    (BASE / "local-results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2), flush=True)
