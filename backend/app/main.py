"""OriginLabs Core FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs" if settings.originlabs_env != "production" else None,
        redoc_url=None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_v1_router)

    @application.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "service": "OriginLabs Core API",
            "version": settings.app_version,
            "health": "/api/v1/health",
        }

    return application


app = create_app()
