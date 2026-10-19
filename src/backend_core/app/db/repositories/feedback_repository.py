"""Store each feedback submission in one database transaction."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, user_id: uuid.UUID, name: str, email: str, comment: str) -> Feedback:
        feedback = Feedback(user_id=user_id, name=name, email=email, comment=comment)
        try:
            self.session.add(feedback)
            await self.session.flush()
            # Load server-generated fields before committing so a failed refresh
            # cannot turn a successful commit into an apparent failed submission.
            await self.session.refresh(feedback)
            await self.session.commit()
            return feedback
        except Exception:
            await self.session.rollback()
            raise
