"""FastAPI dependencies for authentication and RBAC authorization."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.identity.models import Organization, OrganizationMember, User
from app.modules.identity.sessions import resolve_session_user_id


def get_client_ip(request: Request) -> str | None:
    """Extract client IP address respecting reverse proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve and return the authenticated active User from session cookie."""
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no autenticada.",
        )

    user_id = await resolve_session_user_id(raw_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o inválida.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado.",
        )
    return user


async def require_instance_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated user has instance-wide administrator privileges."""
    if not user.is_instance_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador de instancia.",
        )
    return user


async def assert_org_access(
    db: AsyncSession,
    user: User,
    organization_id: uuid.UUID,
    allowed_roles: set[str],
) -> OrganizationMember | None:
    """Verify the organization exists and the user has an allowed role (or is instance admin)."""
    org_result = await db.execute(
        select(Organization.id).where(Organization.id == organization_id)
    )
    if org_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organización no encontrada.",
        )

    member_result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    membership = member_result.scalar_one_or_none()

    if user.is_instance_admin:
        return membership

    if membership is None or membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos suficientes en esta organización.",
        )
    return membership
