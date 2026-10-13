import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_album_service, get_current_user
from app.models.user import User
from app.schemas.album import AlbumDetailResponse, UserAlbumIdsResponse
from app.services.album_service import AlbumService

router = APIRouter()


@router.get(
    "",
    response_model=UserAlbumIdsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user album IDs",
    description="Returns a list of all album IDs belonging to the current user.",
)
async def get_user_albums(
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
) -> UserAlbumIdsResponse:
    """Handle GET /api/v1/albums — list album IDs for authenticated user."""
    return await album_service.get_user_album_ids(current_user.id)


@router.get(
    "/{album_id}",
    response_model=AlbumDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get album details",
    description="Returns full album details with presigned photo URLs.",
)
async def get_album(
    album_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
) -> AlbumDetailResponse:
    """Handle GET /api/v1/albums/{album_id} — retrieve album with photos."""
    return await album_service.get_album(album_id, current_user.id)
