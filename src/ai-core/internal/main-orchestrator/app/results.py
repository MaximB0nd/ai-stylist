from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crypto import Cipher
from app.db import Command, Job, ReceivedMessage
from app.errors import AppError
from app.jobs import scrub_sensitive
from app.pipeline import apply_result, validate_result
from app.schemas import WorkerResult


async def receive_result(sessions: async_sessionmaker[AsyncSession], cipher: Cipher,
                         body: WorkerResult) -> None:
    async with sessions.begin() as session:
        identity = (await session.execute(select(Command.job_id).where(Command.id == body.command_id))).scalar_one_or_none()
        if identity is None:
            raise AppError(404, "COMMAND_NOT_FOUND", "Command not found")
        job = (await session.execute(select(Job).where(Job.id == identity).with_for_update())).scalar_one()
        command = (await session.execute(select(Command).where(Command.id == body.command_id)
                                         .with_for_update())).scalar_one()
        if (command.job_id != body.job_id or command.stage != body.stage or
                command.attempt != body.attempt or command.order_index != body.order_index):
            raise AppError(409, "COMMAND_MISMATCH", "Result does not match command")
        if command.status in ("DONE", "CANCELLED"):
            return
        if job.status in ("COMPLETED", "FAILED", "CANCELLED") and command.stage != "NOTIFICATION":
            command.status = "CANCELLED"
            return
        if await session.get(ReceivedMessage, body.message_id):
            return
        validate_result(command, body, cipher)
        await apply_result(session, cipher, job, command, body)
        session.add(ReceivedMessage(message_id=body.message_id, command_id=command.id))
        command.result_encrypted = cipher.encrypt(body.result) if body.result is not None else None
        command.error_code = body.error.code if body.error else None
        command.error_retryable = body.error.retryable if body.error else None
        command.status = "DONE"
        if job.status in ("COMPLETED", "FAILED", "CANCELLED") and command.stage != "NOTIFICATION":
            await scrub_sensitive(session, job)
