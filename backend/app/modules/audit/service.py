"""Service helpers for recording audit trail events."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.identity.models import User


async def record_audit_event(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor: User | None = None,
    actor_email: str | None = None,
    organization_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an AuditLog entry to the active session."""
    entry = AuditLog(
        actor_user_id=actor.id if actor is not None else None,
        actor_email=actor.email if actor is not None else actor_email,
        organization_id=organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details or {},
    )
    db.add(entry)
    await db.flush()
    return entry
