"""Audit log read-only API endpoints."""

from datetime import datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.audit.models import AuditLog
from app.modules.identity.dependencies import assert_org_access, get_current_user
from app.modules.identity.models import OrganizationMember, User

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogPublic(BaseModel):
    """Serialized audit log record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    organization_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime


@router.get("", response_model=list[AuditLogPublic])
async def list_audit_logs(
    organization_id: uuid.UUID | None = None,
    action: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    """List audit logs scoped by instance admin privileges or org admin roles."""
    stmt = select(AuditLog)

    if organization_id is not None:
        await assert_org_access(db, user, organization_id, {"owner", "admin"})
        stmt = stmt.where(AuditLog.organization_id == organization_id)
    elif not user.is_instance_admin:
        org_ids_result = await db.execute(
            select(OrganizationMember.organization_id).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.role.in_(["owner", "admin"]),
            )
        )
        allowed_org_ids = list(org_ids_result.scalars().all())
        if not allowed_org_ids:
            return []
        stmt = stmt.where(AuditLog.organization_id.in_(allowed_org_ids))

    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action.strip()}%"))

    stmt = stmt.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
