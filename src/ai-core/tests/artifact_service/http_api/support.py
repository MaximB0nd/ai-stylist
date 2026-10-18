from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image

ARTIFACT_ID = "01J8Z8Y7W6V5T4S3R2Q1P0N9B1"


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (3, 2), "red").save(output, format="PNG")
    return output.getvalue()


def expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
