"""Tiny decodable fixtures rather than image signatures followed by fake bytes."""
from io import BytesIO
from PIL import Image


def image_bytes(format="PNG", size=(8, 12), mode="RGB", **save_options):
    with Image.new(mode, size, color=0) as image, BytesIO() as output:
        image.save(output, format=format, **save_options)
        return output.getvalue()
