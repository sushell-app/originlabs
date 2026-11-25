"""Instance administrator endpoints for update checks and notifications."""

from datetime import UTC, datetime
from typing import cast
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import encrypt_secret
from app.core.database import get_db
from app.modules.audit.service import record_audit_event
from app.modules.identity.dependencies import get_client_ip, require_instance_admin
from app.modules.identity.models import User
from app.modules.system.models import InstanceUpdateState, SystemNotification
from app.modules.system.schemas import (
    NotificationsListResponse,
    ReleaseChannel,
    SystemNotificationPublic,
    UpdateSettingsRequest,
    UpdateStatusResponse,
)
from app.modules.system.updates import (
    check_for_updates,
    get_or_create_update_state,
    is_newer_version,
)

system_router = APIRouter(prefix="/system", tags=["system-ops"])


def _serialize_update_status(
    state: InstanceUpdateState,
    *,
    warning: str | None = None,
) -> UpdateStatusResponse:
    settings = get_settings()
    update_available = bool(
        state.latest_available_version
        and is_newer_version(settings.app_version, state.latest_available_version)
    )
    return UpdateStatusResponse(
        current_version=settings.app_version,
        channel=cast(ReleaseChannel, state.channel),
        auto_check_enabled=state.auto_check_enabled,
        releases_feed_configured=bool(settings.originlabs_releases_url),
        update_available=update_available,
        latest_available_version=state.latest_available_version,
        latest_severity=state.latest_severity,
        latest_release_notes_url=state.latest_release_notes_url,
        latest_changelog=list(state.latest_changelog or []),
        last_checked_at=state.last_checked_at,
        webhook_url=state.webhook_url,
        has_webhook_secret=bool(state.webhook_encrypted_secret),
        warning=warning,
    )


@system_router.get("/updates", response_model=UpdateStatusResponse)
async def get_updates_status(
    _: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> UpdateStatusResponse:
    """Return update check state and latest available release for instance admins."""
    state = await get_or_create_update_state(db)
    await db.commit()
    return _serialize_update_status(state)


@system_router.patch("/updates/settings", response_model=UpdateStatusResponse)
async def update_updates_settings(
    payload: UpdateSettingsRequest,
    request: Request,
    admin: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> UpdateStatusResponse:
    """Configure release channel, auto-check flag and optional signed webhook."""
    state = await get_or_create_update_state(db)
    if payload.channel is not None:
        state.channel = payload.channel
    if payload.auto_check_enabled is not None:
        state.auto_check_enabled = payload.auto_check_enabled
    if payload.webhook_url is not None:
        state.webhook_url = payload.webhook_url or None
    if payload.webhook_secret is not None:
        state.webhook_encrypted_secret = (
            encrypt_secret(payload.webhook_secret.strip())
            if payload.webhook_secret.strip()
            else None
        )

    await record_audit_event(
        db,
        action="system.update_settings_updated",
        resource_type="instance_update_state",
        resource_id="1",
        actor=admin,
        ip_address=get_client_ip(request),
        details={
            "channel": state.channel,
            "auto_check_enabled": state.auto_check_enabled,
            "webhook_configured": bool(state.webhook_url),
        },
    )
    await db.commit()
    await db.refresh(state)
    return _serialize_update_status(state)


@system_router.post("/updates/check", response_model=UpdateStatusResponse)
async def trigger_update_check(
    request: Request,
    admin: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> UpdateStatusResponse:
    """Trigger an immediate check against the configured release feed."""
    result = await check_for_updates(db)
    await record_audit_event(
        db,
        action="system.update_checked",
        resource_type="instance_update_state",
        resource_id="1",
        actor=admin,
        ip_address=get_client_ip(request),
        details={
            "update_available": result.update_available,
            "latest_version": result.state.latest_available_version,
        },
    )
    await db.commit()
    return _serialize_update_status(result.state, warning=result.warning)


@system_router.get("/notifications", response_model=NotificationsListResponse)
async def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    _: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationsListResponse:
    """List administrator notifications and unread count."""
    unread_count = int(
        (
            await db.execute(
                select(func.count(SystemNotification.id)).where(
                    SystemNotification.is_read.is_(False)
                )
            )
        ).scalar_one()
        or 0
    )
    items = (
        await db.execute(
            select(SystemNotification)
            .order_by(desc(SystemNotification.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return NotificationsListResponse(
        unread_count=unread_count,
        items=[SystemNotificationPublic.model_validate(item) for item in items],
    )


@system_router.post(
    "/notifications/{notification_id}/read",
    response_model=SystemNotificationPublic,
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    _: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> SystemNotificationPublic:
    """Mark a single administrator notification as read."""
    item = (
        await db.execute(
            select(SystemNotification).where(SystemNotification.id == notification_id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada.",
        )
    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(item)
    return SystemNotificationPublic.model_validate(item)


@system_router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    _: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark all unread administrator notifications as read."""
    await db.execute(
        update(SystemNotification)
        .where(SystemNotification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await db.commit()
