import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import api_router
from server.core.config import settings
from server.core.exceptions import register_exception_handlers
from server.core.logging import setup_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Application factory."""
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    register_exception_handlers(app)
    
    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["Health"])
    def root_health():
        """Root health check."""
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "healthy",
        }

    logger.info(
        "Application started",
        extra={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
        },
    )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
