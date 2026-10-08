from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .common import ArtifactError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ArtifactError)
    async def artifact_error(_request: Request, error: ArtifactError):
        headers = {"Content-Type": "application/problem+json"}
        if error.retry_after is not None:
            headers["Retry-After"] = str(error.retry_after)
        return JSONResponse(
            {
                "type": "about:blank",
                "title": error.code.replace("_", " ").title(),
                "status": error.status,
                "code": error.code,
                "retryable": error.retryable,
            },
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(BotoCoreError)
    @app.exception_handler(ClientError)
    async def storage_error(request: Request, _error: Exception):
        return await artifact_error(request, ArtifactError(502, "STORAGE_UNAVAILABLE", retryable=True))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        malformed = any(item["type"] == "json_invalid" for item in error.errors())
        return await artifact_error(
            request, ArtifactError(400 if malformed else 422, "MALFORMED_REQUEST" if malformed else "VALIDATION_ERROR")
        )
