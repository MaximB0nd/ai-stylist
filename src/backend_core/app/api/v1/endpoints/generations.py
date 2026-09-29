from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, status

from app.core.dependencies import get_current_user, get_generation_service
from app.models.user import User
from app.schemas.generation import GenerationAcceptedResponse, GenerationRequestForm
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
