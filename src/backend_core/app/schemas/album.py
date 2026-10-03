import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict


class PhotoResponse(BaseModel):
    """Single photo within an album response."""

    id: uuid.UUID
    order_index: int
    url: str

    model_config = ConfigDict(from_attributes=True)


class AlbumDetailResponse(BaseModel):
    """Full album detail response per RETRIEVE_ALBUM.md contract."""

    id: uuid.UUID
    title: str
    situation: str
    styles: List[str]
    shoes: List[str]
    impressions: List[str]
    created_at: datetime
    is_archived: bool
    total_photos: int
    photos: List[PhotoResponse]

    model_config = ConfigDict(from_attributes=True)


class UserAlbumIdsResponse(BaseModel):
    """User album IDs response per USER_ALBUM_IDS.md contract."""

    album_ids: List[uuid.UUID]
    total: int
