from fastapi import APIRouter

from app.api.v1.endpoints import albums, auth, generations, internal

api_router = APIRouter()

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"],
)

api_router.include_router(
    generations.router,
    prefix="/generations",
    tags=["Generations"],
)

api_router.include_router(
    albums.router,
    prefix="/albums",
    tags=["Albums"],
)

api_router.include_router(
    internal.router,
    prefix="/internal",
    tags=["Internal"],
)

