"""Health and metadata endpoints for OriginLabs Core API v1."""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory, check_database_health
from app.core.redis import check_redis_health
from app.modules.extensions import CommunityLicenseProvider, build_default_registry
from app.modules.identity.models import User

router = APIRouter(tags=["system"])


class ServiceHealth(BaseModel):
    """Health status for an individual backing service."""

    ok: bool
    error: str | None = None


class HealthResponse(BaseModel):
    """Overall health payload for OriginLabs API and backing services."""

    status: str
    version: str
    environment: str
    services: dict[str, ServiceHealth]


async def _is_setup_required() -> bool:
    """Return True if no users exist yet (or DB is not migrated/reachable yet)."""
    try:
        async with async_session_factory() as session:
            existing = (await session.execute(select(User.id).limit(1))).scalar_one_or_none()
            return existing is None
    except Exception:  # noqa: BLE001
        return True


@router.get("/health", response_model=HealthResponse)
async def health_check() -> JSONResponse:
    """Verify PostgreSQL and Redis connectivity and return service status."""
    settings = get_settings()
    db_ok, db_error = await check_database_health()
    redis_ok, redis_error = await check_redis_health()
    all_ok = db_ok and redis_ok

    payload = HealthResponse(
        status="ok" if all_ok else "degraded",
        version=settings.app_version,
        environment=settings.originlabs_env,
        services={
            "database": ServiceHealth(ok=db_ok, error=db_error),
            "redis": ServiceHealth(ok=redis_ok, error=redis_error),
        },
    )
    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_status, content=payload.model_dump())


@router.get("/meta")
async def instance_meta() -> dict[str, Any]:
    """Return instance metadata, active edition and included core modules."""
    settings = get_settings()
    license_info = CommunityLicenseProvider().get_license()
    extensions = [asdict(item) for item in build_default_registry().list_all()]
    setup_required = await _is_setup_required()
    return {
        "name": "OriginLabs",
        "version": settings.app_version,
        "domain": settings.originlabs_domain,
        "edition": license_info.edition,
        "setup_required": setup_required,
        "modules": extensions,
    }
