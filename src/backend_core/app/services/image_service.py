"""Validate bounded static images and normalize new objects to 8-bit PNG."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from io import BytesIO
from weakref import WeakKeyDictionary

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_PNG_BYTES = 15 * 1024 * 1024
MAX_SIDE = 4096
MIME_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="image-normalize")
_slots = WeakKeyDictionary()


class InvalidImage(ValueError):
    """An image is corrupt or outside the supported image contract."""


class ImageTooLarge(InvalidImage):
    """The compressed source or normalized PNG exceeds its byte budget."""


@asynccontextmanager
async def image_slot():
    """Bound admission before reading sources; share it with result conversion."""
    loop = asyncio.get_running_loop()
    if loop not in _slots:
        _slots[loop] = asyncio.Semaphore(2)
    async with _slots[loop]:
        yield


async def run_image_work(function, *args):
    """Drain cancelled work before returning its admission slot to another job."""
    future = asyncio.get_running_loop().run_in_executor(_executor, function, *args)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        while not future.done():
            try:
                await asyncio.shield(future)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if future.done() and not future.cancelled():
            future.exception()
        raise


class _BoundedPNG(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_PNG_BYTES:
            raise ImageTooLarge("Normalized PNG exceeds 15 MiB")
        return super().write(data)


def _plain_png(data):
    """Fast path only for a complete PNG with no metadata or trailing payload."""
    offset = 8
    while offset + 12 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        offset += size + 12
        if kind not in (b"IHDR", b"IDAT", b"IEND") or offset > len(data):
            return False
        if kind == b"IEND":
            return size == 0 and offset == len(data)
    return False


def normalize_png(data: bytes, declared_mime: str | None = None) -> bytes:
    """Decode fully, reject animation/oversize, strip metadata and encode once.

    Caller must use image_slot and run_image_work in async code. Source MIME,
    when supplied, must agree with the actual JPEG/PNG/WebP decoder.
    """
    if len(data) > MAX_PNG_BYTES:
        raise ImageTooLarge("Image exceeds 15 MiB")
    try:
        with Image.open(BytesIO(data)) as probe:
            if probe.format not in MIME_FORMATS.values():
                raise InvalidImage("Only JPEG, PNG and WebP images are supported")
            if declared_mime is not None and MIME_FORMATS.get(declared_mime) != probe.format:
                raise InvalidImage("Image format does not match its declared Content-Type")
            if not (1 <= probe.width <= MAX_SIDE and 1 <= probe.height <= MAX_SIDE):
                raise InvalidImage("Image dimensions must not exceed 4096 pixels per side")
            if getattr(probe, "n_frames", 1) != 1:
                raise InvalidImage("Animated images are not supported")
            if probe.format == "PNG" and data[24] == 16:
                raise InvalidImage("16-bit PNG is not supported; use an 8-bit image")
            # PNG verify validates chunk checksums; load below checks decoding.
            probe.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            if image.format == "PNG" and image.mode in ("RGB", "RGBA") and data[24] == 8 and not image.info and _plain_png(data):
                return data
            oriented = ImageOps.exif_transpose(image)
            try:
                has_alpha = "A" in oriented.getbands() or "transparency" in oriented.info
                mode = "RGBA" if has_alpha else "RGB"
                converted = oriented.convert(mode)
                try:
                    profile = oriented.info.get("icc_profile")
                    if profile:
                        # Convert color before discarding the source ICC profile.
                        color = oriented if oriented.mode in ("RGB", "RGBA", "CMYK", "LAB") else converted
                        corrected = ImageCms.profileToProfile(
                            color, ImageCms.ImageCmsProfile(BytesIO(profile)),
                            ImageCms.createProfile("sRGB"), outputMode="RGB",
                        )
                        if has_alpha:
                            corrected.putalpha(converted.getchannel("A"))
                        converted.close()
                        converted = corrected
                    converted.info.clear()
                    with _BoundedPNG() as output:
                        converted.save(output, format="PNG", compress_level=3, optimize=False)
                        return output.getvalue()
                finally:
                    converted.close()
            finally:
                oriented.close()
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, ImageCms.PyCMSError) as exc:
        raise InvalidImage("Invalid or damaged image") from exc


async def normalize_result(data: bytes) -> bytes:
    async with image_slot():
        return await run_image_work(normalize_png, data)
