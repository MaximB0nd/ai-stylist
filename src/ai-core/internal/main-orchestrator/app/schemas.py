import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Inputs(StrictModel):
    face_photo_url: HttpUrl
    body_photo_url: HttpUrl
    expires_at: datetime

    @field_validator("face_photo_url", "body_photo_url")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("HTTPS required")
        return value

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value.astimezone(UTC)


class Person(StrictModel):
    age: int = Field(ge=18, le=100)
    height_cm: int = Field(ge=120, le=230)
    gender: Literal["female", "male", "unspecified"]


class Preferences(StrictModel):
    occasion: Literal["casual", "study", "office", "evening", "sport", "travel"]
    styles: list[Literal["classic", "minimalism", "romantic", "streetwear", "sport"]] = Field(max_length=20)
    shoes: list[Literal["loafers", "sneakers", "boots", "heels", "any"]] = Field(max_length=20)
    impressions: list[Literal["confident", "elegant", "relaxed", "bright", "professional"]] = Field(max_length=20)
    description: str = Field(max_length=1000)

    @model_validator(mode="after")
    def unique_lists(self) -> "Preferences":
        for name in ("styles", "shoes", "impressions"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {name}")
        return self


class JobCreate(StrictModel):
    idempotency_key_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_image_count: int = Field(ge=1, le=10)
    inputs: Inputs
    person: Person
    preferences: Preferences

    def normalized_body(self) -> dict:
        return self.model_dump(mode="json", exclude={"idempotency_key_hash", "request_hash"})

    def computed_hash(self) -> str:
        body = json.dumps(self.normalized_body(), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        return hashlib.sha256(body).hexdigest()


class EmptyBody(StrictModel):
    pass


class WorkerError(StrictModel):
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(max_length=256)
    retryable: bool


class WorkerResult(StrictModel):
    contract_version: Literal[1]
    message_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    command_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    job_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    stage: Literal["PREPARATION", "STYLING", "GENERATION", "VERIFICATION", "NOTIFICATION"]
    attempt: int = Field(ge=1, le=4)
    order_index: int | None = Field(default=None, ge=0)
    status: Literal["SUCCEEDED", "FAILED"]
    result: dict | None
    error: WorkerError | None

    @model_validator(mode="after")
    def outcome_matches_status(self) -> "WorkerResult":
        if self.status == "SUCCEEDED" and (self.result is None or self.error is not None):
            raise ValueError("Successful result requires result only")
        if self.status == "FAILED" and (self.result is not None or self.error is None):
            raise ValueError("Failed result requires error only")
        return self
