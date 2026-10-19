"""Create feedback for a user identified by the authentication dependency."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.db.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import FeedbackCreateRequest, FeedbackCreatedResponse


class FeedbackService:
    def __init__(self, feedback_repo: FeedbackRepository) -> None:
        self.feedback_repo = feedback_repo

    async def create(self, user_id: uuid.UUID, data: FeedbackCreateRequest) -> FeedbackCreatedResponse:
        try:
            feedback = await self.feedback_repo.create(
                user_id=user_id, name=data.name, email=str(data.email), comment=data.comment,
            )
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not save feedback. Please try again later.",
            ) from None
        return FeedbackCreatedResponse.model_validate(feedback)
