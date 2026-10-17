import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, UrlConstraints, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputPhoto(StrictModel):
    url: Annotated[AnyUrl, UrlConstraints(max_length=4096, allowed_schemes=["http"])]
    expires_at: datetime

    @field_validator("url")
    @classmethod
    def require_internal_url(cls, value: AnyUrl) -> AnyUrl:
        if value.username or value.password or value.fragment:
            raise ValueError("URL must not contain credentials or fragment")
        return value

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value.astimezone(UTC)


class Person(StrictModel):
    age: int = Field(ge=1, le=120)
    height_cm: int = Field(ge=80, le=240)
    gender: Literal["female", "male"]


class Preferences(StrictModel):
    occasion: Literal["street", "study", "office", "evening"]
    style: Literal["minimal", "classic", "casual", "romantic"]
    shoe: Literal["sneakers", "loafers", "heels", "boots"]
    mood: Literal["confident", "elegant", "relaxed", "bright"]


class Inputs(StrictModel):
    face: InputPhoto
    body: InputPhoto


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
