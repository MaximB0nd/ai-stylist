from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, Field


class GenderEnum(str, Enum):
    FEMALE = "f"
    MALE = "m"


class SituationEnum(str, Enum):
    STREET = "street"
    STUDY = "study"
    OFFICE = "office"
    EVENING = "evening"


# Current AI Core styles, plus the historical REST minimalism alias.
class StyleEnum(str, Enum):
    CASUAL = "casual"
    MINIMAL = "minimal"
    MINIMALISM = "minimalism"
    CLASSIC = "classic"
    ROMANTIC = "romantic"


class ShoesEnum(str, Enum):
    SNEAKERS = "sneakers"
    LOAFERS = "loafers"
    HEELS = "heels"
    BOOTS = "boots"


class ImpressionEnum(str, Enum):
    CONFIDENT = "confident"
    ELEGANT = "elegant"
    RELAXED = "relaxed"
    BRIGHT = "bright"


# Mapping situation -> default album title (Russian)
SITUATION_TITLES: dict[str, str] = {
    "street": "Улица",
    "study": "Учёба",
    "office": "Офис",
    "evening": "Вечер",
}


class GenerationRequestForm(BaseModel):
    """Validated form-data fields for generation request (parsed manually from form).

    Product ranges are narrower than the AI Core contract:
      - age: 18..100 (AI Core accepts 1..120)
      - height: 120..230 cm (AI Core accepts 80..240)

    Styles are limited to the AI Core accepted set:
      minimal, classic, casual, romantic; minimalism is a REST alias.
    """

    age: int = Field(..., ge=18, le=100, description="User age (18–100, product restriction)")
    height: int = Field(..., ge=120, le=230, description="Height in cm (120–230, product restriction)")
    gender: GenderEnum = Field(..., description="Gender: 'f' or 'm'")
    situation: SituationEnum
    styles: StyleEnum = Field(..., description="One style (minimal/classic/casual/romantic; minimalism alias)")
    shoes: ShoesEnum = Field(..., description="Exactly one shoe type")
    impressions: ImpressionEnum = Field(..., description="Exactly one impression")


class GenerationAcceptedResponse(BaseModel):
    """202 Accepted response per contract."""

    generation_id: uuid.UUID
    status: str = "VALIDATING"
    message: str = "Generation request accepted for processing"
    status_poll_url: str


class GenerationStatusResponse(BaseModel):
    """Response model for GET /api/v1/generations/{generation_id}/status."""

    generation_id: uuid.UUID
    status: str
    album_id: Optional[uuid.UUID] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
