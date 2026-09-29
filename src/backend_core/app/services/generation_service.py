import logging
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.db.repositories.album_repository import AlbumRepository
from app.schemas.generation import (
    SITUATION_TITLES,
    GenerationAcceptedResponse,
    GenerationRequestForm,
)
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

# Allowed image content types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


class GenerationService:
    """Service handling generation request business logic."""

    def __init__(
        self,
        album_repo: AlbumRepository,
        storage: StorageService,
    ) -> None:
        self.album_repo = album_repo
        self.storage = storage

    async def create_generation(
        self,
        user_id: uuid.UUID,
        face_photo: UploadFile,
        body_photo: UploadFile,
        form: GenerationRequestForm,
    ) -> GenerationAcceptedResponse:
        """Validate photos, upload to storage, create album, return 202 response."""
        self._validate_photo(face_photo, "face_photo")
        self._validate_photo(body_photo, "body_photo")

        generation_id = uuid.uuid4()
        title = SITUATION_TITLES.get(form.situation.value, form.situation.value)

        # Upload source photos to MinIO
        face_key = f"sources/{user_id}/{generation_id}/face{_extension(face_photo)}"
        body_key = f"sources/{user_id}/{generation_id}/body{_extension(body_photo)}"

        try:
            await self.storage.upload_file(face_key, face_photo)
            await self.storage.upload_file(body_key, body_photo)
        except Exception:
            logger.exception("Failed to upload source photos for generation %s", generation_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to store uploaded photos. Please try again.",
            )

        # Persist album record
        await self.album_repo.create_album(
            user_id=user_id,
            generation_id=generation_id,
            title=title,
            situation=form.situation.value,
            styles=[s.value for s in form.styles],
            shoes=[s.value for s in form.shoes],
            impressions=[i.value for i in form.impressions],
            user_age=form.age,
            user_height=form.height,
            source_face_key=face_key,
            source_body_key=body_key,
        )

        return GenerationAcceptedResponse(
            generation_id=generation_id,
            status="VALIDATING",
            message="Generation request accepted for processing",
            status_poll_url=f"{settings.API_V1_PREFIX}/generations/{generation_id}/status",
        )

    @staticmethod
    def _validate_photo(file: UploadFile, field_name: str) -> None:
        """Validate that uploaded file is an allowed image type."""
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Both photos are required. Missing: {field_name}",
            )
        content_type = file.content_type or ""
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type for {field_name}: {content_type}. Allowed: webp, jpeg, png.",
            )


def _extension(file: UploadFile) -> str:
    """Extract file extension from filename, defaulting to .bin."""
    if file.filename and "." in file.filename:
        return "." + file.filename.rsplit(".", 1)[-1].lower()
    return ".bin"
