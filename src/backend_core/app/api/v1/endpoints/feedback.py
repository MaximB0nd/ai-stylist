"""Authenticated endpoint for feedback submission."""

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, get_feedback_service
from app.models.user import User
from app.schemas.feedback import FeedbackCreateRequest, FeedbackCreatedResponse
from app.services.feedback_service import FeedbackService

router = APIRouter()


@router.post("", response_model=FeedbackCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    data: FeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackCreatedResponse:
    """Save contact details and comment linked only to the authenticated user."""
    return await service.create(current_user.id, data)
