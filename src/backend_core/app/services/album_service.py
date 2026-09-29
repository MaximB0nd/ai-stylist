import uuid
from typing import List

from fastapi import HTTPException, status

from app.db.repositories.album_repository import AlbumRepository
from app.schemas.album import AlbumDetailResponse, PhotoResponse, UserAlbumIdsResponse
from app.services.storage_service import StorageService


class AlbumService:
    """Service handling album retrieval business logic."""

    def __init__(
        self,
        album_repo: AlbumRepository,
        storage: StorageService,
    ) -> None:
        self.album_repo = album_repo
        self.storage = storage

    async def get_album(
        self, album_id: uuid.UUID, current_user_id: uuid.UUID
    ) -> AlbumDetailResponse:
        """Retrieve album with presigned photo URLs. Enforce ownership."""
        album = await self.album_repo.get_by_id_with_photos(album_id)

        if not album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Album not found or deleted.",
            )

        if album.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this album is forbidden.",
            )

        # Generate presigned URLs for each photo
        photos: List[PhotoResponse] = []
        for photo in album.photos:
            url = self.storage.presigned_url(photo.object_key)
            photos.append(
                PhotoResponse(
                    id=photo.id,
                    order_index=photo.order_index,
                    url=url,
                )
            )

        return AlbumDetailResponse(
            id=album.id,
            title=album.title,
            situation=album.situation,
            styles=album.styles,
            shoes=album.shoes,
            impressions=album.impressions,
            created_at=album.created_at,
            is_archived=album.is_archived,
            total_photos=album.total_photos,
            photos=photos,
        )

    async def get_user_album_ids(
        self, user_id: uuid.UUID
    ) -> UserAlbumIdsResponse:
        """Return list of album IDs for the current user."""
        album_ids = await self.album_repo.get_user_album_ids(user_id)
        return UserAlbumIdsResponse(
            album_ids=album_ids,
            total=len(album_ids),
        )
