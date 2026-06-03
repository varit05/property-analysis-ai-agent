from fastapi import APIRouter

from server.api.admin import admin_router
from server.api.properties import router as properties_router

api_router = APIRouter()

api_router.include_router(properties_router, prefix="/properties", tags=["Properties"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])

__all__ = ["api_router"]
