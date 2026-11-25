"""Version 1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.modules.audit.router import router as audit_router
from app.modules.identity.router import auth_router, internal_router, orgs_router
from app.modules.projects.router import projects_router
from app.modules.system.router import system_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(orgs_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(system_router)
api_v1_router.include_router(internal_router)
api_v1_router.include_router(audit_router)
