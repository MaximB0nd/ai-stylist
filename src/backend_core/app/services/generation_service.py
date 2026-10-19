import asyncio
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
from app.services.retry_policy import is_retryable_ai_error
from app.services.image_service import (
    InvalidImage, ImageTooLarge, MAX_SOURCE_BYTES, image_slot, normalize_png, run_image_work,
)

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
        generation_id = uuid.uuid4()
        title = SITUATION_TITLES.get(form.situation.value, form.situation.value)
        face_key = f"sources/{user_id}/{generation_id}/face.png"
        body_key = f"sources/{user_id}/{generation_id}/body.png"

        # Hold admission through uploads so waiting requests do not accumulate
        # decoded rasters or converted PNG buffers while MinIO is unavailable.
        async with image_slot():
            face_png = await self._prepare_photo(face_photo, "face_photo")
            body_png = await self._prepare_photo(body_photo, "body_photo")
            attempted = []
            try:
                for key, content in ((face_key, face_png), (body_key, body_png)):
                    attempted.append(key)
                    await self.storage.upload_bytes(key, content, content_type="image/png")
            except BaseException as exc:
                await self._cleanup_sources(attempted)
                if isinstance(exc, asyncio.CancelledError):
                    raise
                logger.warning("Failed to store sources for generation %s", generation_id)
                raise HTTPException(status_code=502, detail="Failed to store uploaded photos. Please try again.") from None

            try:
                album = await self.album_repo.create_album(
                    user_id=user_id, generation_id=generation_id, title=title,
                    situation=form.situation.value, styles=[form.styles.value],
                    shoes=[form.shoes.value], impressions=[form.impressions.value],
                    user_age=form.age, user_height=form.height, gender=form.gender.value,
                    source_face_key=face_key, source_body_key=body_key, status="VALIDATING",
                )
            except Exception:
                # A commit can succeed even if its response is lost. Keep source
                # objects on an ambiguous DB error; lifecycle removes orphans.
                logger.warning("Could not persist source metadata for generation %s", generation_id)
                raise
        del face_png, body_png, content

        current_status = "VALIDATING"

        # Dispatch job to AI Core if client is configured
        if self.ai_client:
            from app.services.generation_dispatch import dispatch_generation
            from app.services.generation_lease import keep_lease
            token = await self.album_repo.claim_work(album.id, ["VALIDATING"])
            try:
                if token is not None:
                    async with keep_lease(album.id, token):
                        current_status = await dispatch_generation(
                            album, self.album_repo, self.storage, self.ai_client, token
                        ) or "VALIDATING"
            except Exception as exc:
                if is_retryable_ai_error(exc):
                    # The persisted album and dispatch inputs are the durable retry queue.
                    await self.album_repo.finish_work(
                        album.id, token,
                        error_message=f"Temporary AI Core dispatch failure: {exc}"[:500],
                    )
                    current_status = album.status
                    logger.warning("AI Core dispatch deferred for generation %s", generation_id)
                else:
                    await self.album_repo.finish_work(
                        album.id, token, status="FAILED",
                        error_message=f"Failed to dispatch job to AI Core: {exc}"[:500],
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Failed to dispatch generation task to AI cluster: {exc}",
                    ) from exc


        return GenerationAcceptedResponse(
            generation_id=generation_id,
            status=current_status,
            message="Generation request accepted for processing",
            status_poll_url=f"{settings.API_V1_PREFIX}/generations/{generation_id}/status",
        )

    async def _cleanup_sources(self, keys):
        for key in keys:
            try:
                await self.storage.delete_object(key)
            except Exception:
                logger.warning("Could not clean failed source upload")

    @staticmethod
    async def _prepare_photo(file: UploadFile, field_name: str) -> bytes:
        """Read a bounded upload and validate/convert it under image admission."""
        if not file or not file.filename:
            raise HTTPException(status_code=422, detail=f"Both photos are required. Missing: {field_name}")
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid file type for {field_name}. Allowed: webp, jpeg, png.")
        data = await file.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail=f"{field_name} exceeds the maximum allowed size of 10 MiB.")
        try:
            return await run_image_work(normalize_png, data, file.content_type)
        except ImageTooLarge as exc:
            raise HTTPException(status_code=413, detail=f"{field_name}: {exc}") from None
        except InvalidImage as exc:
            raise HTTPException(status_code=400, detail=f"Invalid image content for {field_name}: {exc}") from None
