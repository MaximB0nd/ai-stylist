from io import BytesIO

import pytest
from PIL import Image

from internal.artifact_service.image import inspect_image


def png_bytes(size: tuple[int, int] = (2, 3)) -> bytes:
    image = Image.new("RGB", size, "red")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_accepts_png_and_reports_geometry():
    info = inspect_image(png_bytes(), "image/png")
    assert (info.media_type, info.width, info.height) == ("image/png", 2, 3)


def test_rejects_content_type_mismatch():
    with pytest.raises(ValueError):
        inspect_image(png_bytes(), "image/jpeg")


def test_rejects_dimensions_above_limit():
    with pytest.raises(ValueError):
        inspect_image(png_bytes((4097, 1)))
