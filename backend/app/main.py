"""OriginLabs Core FastAPI application entrypoint."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

    static_dir = (
        Path(settings.originlabs_static_dir).resolve()
        if settings.originlabs_static_dir
        else None
    )
    if static_dir is not None and (static_dir / "index.html").is_file():
        spa_dir: Path = static_dir
        spa_index: Path = spa_dir / "index.html"
        assets_dir = spa_dir / "assets"
        if assets_dir.is_dir():
            application.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="static-assets",
            )

        @application.get("/", include_in_schema=False)
        async def serve_spa_root() -> FileResponse:
            return FileResponse(spa_index)

        @application.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            if (
                full_path == "api"
                or full_path.startswith("api/")
                or full_path == "ws"
                or full_path.startswith("ws/")
            ):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = (spa_dir / full_path).resolve()
            if candidate.is_relative_to(spa_dir) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(spa_index)
    else:

        @application.get("/", tags=["root"])
        async def root() -> dict[str, str]:
            return {
                "service": "OriginLabs Core API",
                "version": settings.app_version,
                "health": "/api/v1/health",
            }

    return application


app = create_app()
