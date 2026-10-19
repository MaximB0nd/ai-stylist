"""Verify decoded PNG output, image limits, cancellation and pipeline integration."""

import asyncio
from contextlib import asynccontextmanager
import hashlib
import random
from io import BytesIO
import struct
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid
import zlib

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageCms, PngImagePlugin
import pytest

from app.services import image_service, generation_results
from app.services.generation_service import GenerationService
from app.schemas.generation import GenerationRequestForm
from tests.image_fixtures import image_bytes
from tests.test_generations import InMemoryAlbumRepository, InMemoryStorageService, FAKE_USER_ID


@pytest.mark.parametrize("format,mime", [("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("PNG", "image/png")])
def test_normalize_produces_real_png(format, mime):
    data = image_bytes(format)
    output = image_service.normalize_png(data, mime)
    with Image.open(BytesIO(output)) as image:
        image.load()
        assert image.format == "PNG" and image.mode == "RGB" and image.size == (8, 12)
    if format == "PNG":
        assert output is data


def test_orientation_applied_and_metadata_removed():
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private metadata"
    data = image_bytes("JPEG", size=(8, 12), exif=exif)
    with Image.open(BytesIO(image_service.normalize_png(data))) as image:
        assert image.size == (12, 8)
        assert not image.getexif() and not image.info


def test_alpha_and_palette_transparency_preserved():
    for mode in ("RGBA", "P"):
        options = {"transparency": 0} if mode == "P" else {}
        data = image_bytes("PNG", mode=mode, **options)
        with Image.open(BytesIO(image_service.normalize_png(data))) as image:
            assert image.mode == "RGBA" and image.getpixel((0, 0))[3] == 0


def test_color_profile_is_applied_and_removed():
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    data = image_bytes("PNG", icc_profile=profile)
    with Image.open(BytesIO(image_service.normalize_png(data))) as image:
        assert image.mode == "RGB" and "icc_profile" not in image.info


def test_color_profile_conversion_preserves_alpha():
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    data = image_bytes("PNG", mode="RGBA", icc_profile=profile)
    with Image.open(BytesIO(image_service.normalize_png(data))) as image:
        assert image.mode == "RGBA" and image.getpixel((0, 0))[3] == 0


def test_png_text_and_trailing_payload_are_removed():
    info = PngImagePlugin.PngInfo()
    info.add_text("private", "location")
    data = image_bytes("PNG", pnginfo=info)
    for source in (data, image_bytes() + b"trailing payload"):
        output = image_service.normalize_png(source)
        with Image.open(BytesIO(output)) as image:
            assert not image.info
        assert output.endswith(b"IEND\xaeB`\x82")


@pytest.mark.parametrize("data", [b"", b"not an image", b"\xff\xd8\xff\xe0fake", image_bytes()[:-12], image_bytes("JPEG")[:50]])
def test_corrupt_images_rejected(data):
    with pytest.raises(image_service.InvalidImage):
        image_service.normalize_png(data)


def test_declared_mime_must_match_decoder():
    with pytest.raises(image_service.InvalidImage, match="Content-Type"):
        image_service.normalize_png(image_bytes("JPEG"), "image/png")


def test_animation_rejected():
    with Image.new("RGB", (4, 4), "red") as first, Image.new("RGB", (4, 4), "blue") as second, BytesIO() as output:
        first.save(output, format="PNG", save_all=True, append_images=[second], loop=0, duration=20)
        with pytest.raises(image_service.InvalidImage, match="Animated"):
            image_service.normalize_png(output.getvalue())


def test_dimensions_checked_before_decode():
    source = bytearray(image_bytes())
    source[16:20] = struct.pack(">I", 4097)
    source[29:33] = struct.pack(">I", zlib.crc32(source[12:29]))
    with pytest.raises(image_service.InvalidImage, match="4096"):
        image_service.normalize_png(bytes(source))
    image_service.normalize_png(image_bytes(size=(4096, 1)))


def test_16_bit_png_rejected_without_clipping_values():
    with pytest.raises(image_service.InvalidImage, match="16-bit"):
        image_service.normalize_png(image_bytes("PNG", mode="I;16"))


def test_compressed_output_budget_is_enforced_while_encoding(monkeypatch):
    # A noisy image compresses poorly; JPEG source is smaller than its PNG.
    pixels = random.Random(0).randbytes(64 * 64 * 3)
    with Image.frombytes("RGB", (64, 64), pixels) as image, BytesIO() as output:
        image.save(output, format="JPEG", quality=10)
        source = output.getvalue()
    assert len(image_service.normalize_png(source)) > len(source) + 1
    monkeypatch.setattr(image_service, "MAX_PNG_BYTES", len(source) + 1)
    with pytest.raises(image_service.ImageTooLarge):
        image_service.normalize_png(source)


async def test_processing_limit_and_cancellation_draining():
    release = threading.Event()
    lock = threading.Lock()
    active = peak = 0

    def work():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            release.wait(3)
        finally:
            with lock:
                active -= 1

    async def job():
        async with image_service.image_slot():
            await image_service.run_image_work(work)

    jobs = [asyncio.create_task(job()) for _ in range(3)]
    try:
        async with asyncio.timeout(2):
            while active < 2:
                await asyncio.sleep(0.005)
        jobs[0].cancel()
        await asyncio.sleep(0.02)
        assert not jobs[0].done() and peak == active == 2
        jobs[0].cancel()
        await asyncio.sleep(0.02)
        assert not jobs[0].done() and peak == 2
    finally:
        release.set()
        await asyncio.gather(*jobs, return_exceptions=True)
    assert active == 0 and peak == 2


def form():
    return GenerationRequestForm(age=25, height=175, gender="m", situation="office",
                                 styles="casual", shoes="loafers", impressions="confident")


def photo(data=None, mime="image/jpeg"):
    return UploadFile(filename="photo", file=BytesIO(data if data is not None else image_bytes("JPEG")),
                      headers={"content-type": mime})


async def test_invalid_second_source_writes_nothing():
    repo, storage = InMemoryAlbumRepository(), InMemoryStorageService()
    with pytest.raises(HTTPException) as error:
        await GenerationService(repo, storage).create_generation(FAKE_USER_ID, photo(), photo(b"invalid"), form())
    assert error.value.status_code == 400 and not storage.uploads and not repo.albums


async def test_sources_and_ai_urls_use_real_png():
    repo, storage = InMemoryAlbumRepository(), InMemoryStorageService()
    ai = SimpleNamespace(create_job=AsyncMock(return_value={"job_id": str(uuid.uuid4()), "status": "QUEUED"}))
    await GenerationService(repo, storage, ai).create_generation(
        FAKE_USER_ID, photo(), photo(image_bytes("WEBP"), "image/webp"), form(),
    )
    assert len(storage.uploads) == 2
    for key, content in storage.uploads.items():
        assert key.endswith(".png")
        with Image.open(BytesIO(content)) as image:
            assert image.format == "PNG"
    kwargs = ai.create_job.await_args.kwargs
    assert kwargs["face_photo_url"].split("?")[0].endswith("face.png")
    assert kwargs["body_photo_url"].split("?")[0].endswith("body.png")


async def test_source_upload_failure_cleans_successful_and_uncertain_put():
    repo, storage = InMemoryAlbumRepository(), InMemoryStorageService()
    original = storage.upload_bytes

    async def upload(key, content, **kwargs):
        await original(key, content, **kwargs)
        if key.endswith("body.png"):
            raise ConnectionError("response lost after PUT")

    storage.upload_bytes = upload
    with pytest.raises(HTTPException) as error:
        await GenerationService(repo, storage).create_generation(FAKE_USER_ID, photo(), photo(), form())
    assert error.value.status_code == 502 and not storage.uploads and not repo.albums


async def test_input_size_and_output_size_errors_are_413(monkeypatch):
    repo, storage = InMemoryAlbumRepository(), InMemoryStorageService()
    monkeypatch.setattr("app.services.generation_service.MAX_SOURCE_BYTES", 10)
    with pytest.raises(HTTPException) as error:
        await GenerationService(repo, storage).create_generation(FAKE_USER_ID, photo(), photo(), form())
    assert error.value.status_code == 413 and not storage.uploads


async def test_results_checksum_precedes_conversion_and_png_is_saved(monkeypatch):
    original = image_bytes("JPEG")
    repo = SimpleNamespace(complete_with_photos=AsyncMock(return_value=True), finish_work=AsyncMock())

    @asynccontextmanager
    async def sessions():
        yield object()

    class Response:
        status_code = 200
        async def aiter_bytes(self):
            yield original

    class Http:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        @asynccontextmanager
        async def stream(self, *args):
            yield Response()

    monkeypatch.setattr(generation_results, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(generation_results.httpx, "AsyncClient", lambda **kwargs: Http())
    monkeypatch.setattr("app.db.repositories.album_repository.AlbumRepository", lambda **kwargs: repo)
    monkeypatch.setattr("app.services.generation_cleanup.cleanup_attempt", AsyncMock())
    item = {"order_index": 0, "download_url": "http://images/result", "checksum_sha256": hashlib.sha256(original).hexdigest()}
    ai = SimpleNamespace(get_job=AsyncMock(return_value={
        "status": "COMPLETED", "result_delivery_status": "AVAILABLE", "requested_image_count": 1, "results": [item],
    }), acknowledge_results=AsyncMock())
    storage = SimpleNamespace(upload_bytes=AsyncMock())
    await generation_results._store_results_owned(uuid.uuid4(), uuid.uuid4(), ai, storage, uuid.uuid4())
    args = storage.upload_bytes.await_args
    assert args.args[0].endswith("look_00.png") and args.kwargs["content_type"] == "image/png"
    with Image.open(BytesIO(args.args[1])) as image:
        assert image.format == "PNG"
    ai.acknowledge_results.assert_awaited_once()
    item["checksum_sha256"] = "0" * 64
    storage.upload_bytes.reset_mock()
    ai.acknowledge_results.reset_mock()
    await generation_results._store_results_owned(uuid.uuid4(), uuid.uuid4(), ai, storage, uuid.uuid4())
    storage.upload_bytes.assert_not_awaited()
    ai.acknowledge_results.assert_not_awaited()
    assert repo.finish_work.await_args.kwargs["status"] == "FAILED"
