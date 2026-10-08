from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageCms, UnidentifiedImageError


@dataclass(frozen=True)
class ImageInfo:
    media_type: str
    width: int
    height: int


class ImageError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EIGHT_BIT_MODES = {"L", "LA", "P", "RGB", "RGBA", "CMYK", "YCbCr"}


def inspect_image(
    data: bytes,
    expected_type: str | None = None,
    *,
    max_dimension: int = 4096,
    max_pixels: int = 4096 * 4096,
    max_exif_bytes: int = 1024 * 1024,
    max_icc_bytes: int = 1024 * 1024,
) -> ImageInfo:
    try:
        with Image.open(BytesIO(data)) as image:
            media_type = MEDIA_TYPES.get(image.format)
            if media_type is None:
                raise ImageError("UNSUPPORTED_IMAGE_TYPE")
            if expected_type is not None and media_type != expected_type:
                raise ImageError("UNSUPPORTED_IMAGE_TYPE")
            width, height = image.size
            if (
                width <= 0
                or height <= 0
                or width > max_dimension
                or height > max_dimension
                or width * height > max_pixels
                or getattr(image, "n_frames", 1) != 1
                or image.mode not in EIGHT_BIT_MODES
            ):
                raise ImageError("IMAGE_DIMENSIONS_EXCEEDED")
            exif = image.info.get("exif", b"")
            icc = image.info.get("icc_profile", b"")
            if len(exif) > max_exif_bytes or len(icc) > max_icc_bytes:
                raise ImageError("IMAGE_DIMENSIONS_EXCEEDED")
            image.getexif()
            if icc:
                ImageCms.ImageCmsProfile(BytesIO(icc))
            image.load()
            return ImageInfo(media_type, width, height)
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageError("UNPROCESSABLE_IMAGE") from exc
