import uuid
from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator


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
    styles: List[StyleEnum] = Field(..., min_length=1, max_length=2)
    shoes: List[ShoesEnum] = Field(..., min_length=1, max_length=2)
    impressions: List[ImpressionEnum] = Field(..., min_length=1, max_length=2)

    @field_validator("styles", "shoes", "impressions", mode="before")
    @classmethod
    def parse_json_string(cls, v: object) -> object:
        """Accept both JSON array strings and plain lists from form-data."""
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                raise ValueError("Must be a valid JSON array")
            if not isinstance(parsed, list):
                raise ValueError("Must be a JSON array")
            return parsed
        return v


class GenerationAcceptedResponse(BaseModel):
    """202 Accepted response per contract."""

    generation_id: uuid.UUID
    status: str = "VALIDATING"
    message: str = "Generation request accepted for processing"
    status_poll_url: str
