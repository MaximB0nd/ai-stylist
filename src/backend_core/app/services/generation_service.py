from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.db.repositories.album_repository import AlbumRepository
from app.schemas.generation import (
    SITUATION_TITLES,
    GenerationAcceptedResponse,
    GenerationRequestForm,
)
from app.services.ai_core_client import AICoreClient
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
        ai_client: Optional[AICoreClient] = None,
    ) -> None:
        self.album_repo = album_repo
        self.storage = storage
        self.ai_client = ai_client

    async def create_generation(
        self,
        user_id: uuid.UUID,
        face_photo: UploadFile,
        body_photo: UploadFile,
        form: GenerationRequestForm,
    ) -> GenerationAcceptedResponse:
        """Validate photos, upload to storage, create album, dispatch to AI Core, return 202 response."""
        await self._validate_photo(face_photo, "face_photo")
        await self._validate_photo(body_photo, "body_photo")


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

        # Persist album record with initial status VALIDATING
        album = await self.album_repo.create_album(
            user_id=user_id,
            generation_id=generation_id,
            title=title,
            situation=form.situation.value,
            styles=[form.styles.value],
            shoes=[form.shoes.value],
            impressions=[form.impressions.value],
            user_age=form.age,
            user_height=form.height,
            gender=form.gender.value,
            source_face_key=face_key,
            source_body_key=body_key,
            status="VALIDATING",
        )

        current_status = "VALIDATING"

        # Dispatch job to AI Core if client is configured
        if self.ai_client:
            try:
                face_url = self.storage.presigned_url(face_key)
                body_url = self.storage.presigned_url(body_key)
                ttl = getattr(self.storage, "presigned_ttl", settings.MINIO_PRESIGNED_TTL)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

                job_data = await self.ai_client.create_job(
                    generation_id=generation_id,
                    face_photo_url=face_url,
                    body_photo_url=body_url,
                    expires_at=expires_at,
                    age=form.age,
                    height_cm=form.height,
                    gender=form.gender.value,
                    situation=form.situation.value,
                    styles=[form.styles.value],
                    shoes=[form.shoes.value],
                    impressions=[form.impressions.value],
                )
                ai_job_id_raw = job_data.get("job_id")
                ai_job_id = uuid.UUID(ai_job_id_raw) if ai_job_id_raw else None
                current_status = job_data.get("status", "QUEUED")
                await self.album_repo.update_status(
                    album_id=album.id,
                    status=current_status,
                    ai_job_id=ai_job_id,
                )
            except Exception as exc:
                logger.warning(
                    "Could not dispatch job to AI Core for generation %s: %s",
                    generation_id,
                    exc,
                )

        return GenerationAcceptedResponse(
            generation_id=generation_id,
            status=current_status,
            message="Generation request accepted for processing",
            status_poll_url=f"{settings.API_V1_PREFIX}/generations/{generation_id}/status",
        )

    @staticmethod
    async def _validate_photo(file: UploadFile, field_name: str) -> None:
        """Validate that uploaded file is an allowed image type and matches magic bytes."""
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

        # Validate magic bytes / file signature
        header = await file.read(16)
        await file.seek(0)

        is_jpeg = header.startswith(b"\xff\xd8\xff")
        is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
        is_webp = header[:4] == b"RIFF" and header[8:12] == b"WEBP"

        if not (is_jpeg or is_png or is_webp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file content for {field_name}: file signature (magic bytes) does not match image format (JPEG, PNG, WEBP).",
            )




def _extension(file: UploadFile) -> str:
    """Extract file extension from filename, defaulting to .bin."""
    if file.filename and "." in file.filename:
        return "." + file.filename.rsplit(".", 1)[-1].lower()
    return ".bin"
