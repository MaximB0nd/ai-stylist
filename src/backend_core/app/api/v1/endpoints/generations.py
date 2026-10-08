import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, status

from app.core.dependencies import get_album_repository, get_current_user, get_generation_service
from app.db.repositories.album_repository import AlbumRepository
from app.models.user import User
from app.schemas.generation import (
    GenerationAcceptedResponse,
    GenerationRequestForm,
    GenerationStatusResponse,
)
from app.services.generation_service import GenerationService

router = APIRouter()


@router.post(
    "",
    response_model=GenerationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request generation",
    description="Accepts two source photos with parameters and queues a generation task.",
)
async def create_generation(
    face_photo: UploadFile = File(..., description="Face portrait photo (webp/jpeg/png)"),
    body_photo: UploadFile = File(..., description="Full body photo (webp/jpeg/png)"),
    age: int = Form(...),
    height: int = Form(...),
    gender: str = Form(...),
    situation: str = Form(...),
    styles: str = Form(...),
    shoes: str = Form(...),
    impressions: str = Form(...),
    current_user: User = Depends(get_current_user),
    generation_service: GenerationService = Depends(get_generation_service),
) -> GenerationAcceptedResponse:
    """Handle POST /api/v1/generations — create a new generation request."""
    # Parse and validate form fields via Pydantic schema
    try:
        form = GenerationRequestForm(
            age=age,
            height=height,
            gender=gender,
            situation=situation,
            styles=styles,
            shoes=shoes,
            impressions=impressions,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return await generation_service.create_generation(
        user_id=current_user.id,
        face_photo=face_photo,
        body_photo=body_photo,
        form=form,
    )


@router.get(
    "/{generation_id}/status",
    response_model=GenerationStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get generation status",
    description="Returns processing status of a generation request for the current user.",
)
async def get_generation_status(
    generation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    album_repo: AlbumRepository = Depends(get_album_repository),
) -> GenerationStatusResponse:
    """Handle GET /api/v1/generations/{generation_id}/status."""
    album = await album_repo.get_by_generation_id(generation_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found.",
        )
    if album.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this generation.",
        )
    return GenerationStatusResponse(
        generation_id=album.generation_id,
        status=album.status,
        album_id=album.id if album.status == "COMPLETED" else None,
        error_message=album.error_message,
        created_at=album.created_at,
        updated_at=album.updated_at,
    )
