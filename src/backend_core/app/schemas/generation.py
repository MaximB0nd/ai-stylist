import uuid
from enum import Enum

from pydantic import BaseModel, Field


class GenderEnum(str, Enum):
    FEMALE = "f"
    MALE = "m"


class SituationEnum(str, Enum):
    STREET = "street"
    STUDY = "study"
    OFFICE = "office"
    EVENING = "evening"


class StyleEnum(str, Enum):
    MINIMALISM = "minimalism"
    CLASSIC = "classic"
    CASUAL = "casual"
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
    """Validated form-data fields for generation request (parsed manually from form)."""

    age: int = Field(..., ge=1, le=150, description="User age")
    height: int = Field(..., ge=50, le=300, description="Height in cm")
    gender: GenderEnum = Field(..., description="Gender: 'f' or 'm'")
    situation: SituationEnum
    styles: StyleEnum = Field(..., description="Exactly one style")
    shoes: ShoesEnum = Field(..., description="Exactly one shoe type")
    impressions: ImpressionEnum = Field(..., description="Exactly one impression")


class GenerationAcceptedResponse(BaseModel):
    """202 Accepted response per contract."""

    generation_id: uuid.UUID
    status: str = "VALIDATING"
    message: str = "Generation request accepted for processing"
    status_poll_url: str
