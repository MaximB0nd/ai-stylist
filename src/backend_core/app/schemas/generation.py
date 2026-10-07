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


# Styles accepted by AI Core contract.
# AI Core allows: classic, minimalism, romantic, streetwear, sport.
# "casual" was previously accepted here but is NOT a valid AI Core style
# and caused guaranteed rejections after photo upload.
class StyleEnum(str, Enum):
    MINIMALISM = "minimalism"
    CLASSIC = "classic"
    STREETWEAR = "streetwear"
    ROMANTIC = "romantic"
    SPORT = "sport"


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

    Ranges are aligned with the AI Core contract:
      - age: 18..100   (AI Core rejects < 18 and > 100)
      - height: 120..230 cm  (AI Core rejects < 120 and > 230)

    Styles are limited to the AI Core accepted set:
      classic, minimalism, romantic, streetwear, sport.
    """

    age: int = Field(..., ge=18, le=100, description="User age (18–100, per AI Core contract)")
    height: int = Field(..., ge=120, le=230, description="Height in cm (120–230, per AI Core contract)")
    gender: GenderEnum = Field(..., description="Gender: 'f' or 'm'")
    situation: SituationEnum
    styles: StyleEnum = Field(..., description="One style (classic/minimalism/romantic/streetwear/sport)")
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
