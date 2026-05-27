from fastapi import APIRouter

from server.api.properties import router as properties_router

api_router = APIRouter()

api_router.include_router(properties_router, prefix="/properties", tags=["Properties"])


__all__ = ["api_router"]
