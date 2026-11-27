"""Instance administrator endpoints for updates, notifications, metrics and backups."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import encrypt_secret
from app.core.database import get_db
from app.modules.audit.service import record_audit_event
from app.modules.identity.dependencies import get_client_ip, require_instance_admin
from app.modules.identity.models import User
from app.modules.system.backups import (
    BackupProvider,
    run_restic_backup,
    validate_backup_repository,
)
from app.modules.system.models import (
    BackupConfig,
    BackupSnapshot,
    InstanceUpdateState,
    SystemNotification,
)
from app.modules.system.monitoring import collect_host_metrics, evaluate_admission
from app.modules.system.schemas import (
    AdmissionStatusPublic,
    BackupConfigPublic,
    BackupConfigUpdateRequest,
    BackupSnapshotPublic,
    HostMetricsResponse,
    NotificationsListResponse,
    ReleaseChannel,
    SystemNotificationPublic,
    UpdateApplyRequest,
    UpdateApplyResponse,
    UpdateSettingsRequest,
    UpdateStatusResponse,
)
from app.modules.system.updater import trigger_self_update, validate_target_version
from app.modules.system.updates import (
    check_for_updates,
    get_or_create_update_state,
    is_newer_version,
)
from app.modules.workspaces.models import Workspace
from app.modules.workspaces.orchestrator import WORKSPACE_CLASS_SPECS, WorkspaceClass

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


def _serialize_backup_config(config: BackupConfig) -> BackupConfigPublic:
    return BackupConfigPublic(
        enabled=config.enabled,
        provider=cast(BackupProvider, config.provider),
        repository=config.repository,
        schedule_cron=config.schedule_cron,
        retention_daily=config.retention_daily,
        retention_weekly=config.retention_weekly,
        has_password=bool(config.encrypted_password),
        has_s3_credentials=bool(config.encrypted_s3_access_key and config.encrypted_s3_secret_key),
        last_backup_at=config.last_backup_at,
        updated_at=config.updated_at,
    )


async def get_or_create_backup_config(db: AsyncSession) -> BackupConfig:
    """Load singleton BackupConfig row, creating defaults if missing."""
    config = (
        await db.execute(select(BackupConfig).where(BackupConfig.id == 1))
    ).scalar_one_or_none()
    if config is None:
        config = BackupConfig(id=1)
        db.add(config)
        await db.flush()
    return config


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


@system_router.post(
    "/updates/apply",
    response_model=UpdateApplyResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def apply_system_update(
    request: Request,
    payload: UpdateApplyRequest | None = None,
    admin: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> UpdateApplyResponse:
    """Launch detached Docker Compose updater to upgrade OriginLabs in 1 click."""
    settings = get_settings()
    state = await get_or_create_update_state(db)
    raw_target = (
        (payload.target_version if payload else None)
        or state.latest_available_version
        or ""
    )

    try:
        clean_target = validate_target_version(raw_target)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        launch = await asyncio.to_thread(trigger_self_update, clean_target)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    db.add(
        SystemNotification(
            category="update",
            severity="info",
            title=f"Actualización iniciada: v{launch.target_version}",
            message=(
                f"Se lanzó la actualización desde {settings.app_version} hacia "
                f"v{launch.target_version} ({launch.target_image})."
            ),
            target_version=launch.target_version,
            details={"updater_container_id": launch.updater_container_id},
        )
    )
    await record_audit_event(
        db,
        action="system.update_apply_started",
        resource_type="instance_update_state",
        resource_id="1",
        actor=admin,
        ip_address=get_client_ip(request),
        details={
            "from_version": settings.app_version,
            "target_version": launch.target_version,
            "target_image": launch.target_image,
        },
    )
    await db.commit()

    return UpdateApplyResponse(
        accepted=True,
        from_version=settings.app_version,
        target_version=launch.target_version,
        target_image=launch.target_image,
        updater_container_id=launch.updater_container_id,
        message=(
            f"Actualizando a v{launch.target_version}. El servidor se reiniciará en unos "
            "segundos."
        ),
    )


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


@system_router.get("/metrics", response_model=HostMetricsResponse)
async def get_system_metrics(
    _: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> HostMetricsResponse:
    """Return live host CPU/RAM/disk telemetry and workspace admission evaluation."""
    running = (
        await db.execute(select(Workspace).where(Workspace.status == "running"))
    ).scalars().all()
    alloc_cpu = sum(
        WORKSPACE_CLASS_SPECS[cast(WorkspaceClass, ws.workspace_class)].cpu_cores
        for ws in running
    )
    alloc_ram = sum(
        WORKSPACE_CLASS_SPECS[cast(WorkspaceClass, ws.workspace_class)].ram_mb
        for ws in running
    )
    metrics = await asyncio.to_thread(
        collect_host_metrics,
        running_workspaces=len(running),
        allocated_cpu_cores=alloc_cpu,
        allocated_ram_mb=alloc_ram,
    )
    workspace_classes: tuple[WorkspaceClass, ...] = ("light", "standard", "heavy")
    decisions = [evaluate_admission(metrics, ws_cls) for ws_cls in workspace_classes]
    return HostMetricsResponse(
        hostname=metrics.hostname,
        os_name=metrics.os_name,
        arch=metrics.arch,
        cpu_cores=metrics.cpu_cores,
        load_avg_1m=metrics.load_avg_1m,
        ram_total_mb=metrics.ram_total_mb,
        ram_available_mb=metrics.ram_available_mb,
        ram_used_pct=metrics.ram_used_pct,
        disk_total_gb=metrics.disk_total_gb,
        disk_free_gb=metrics.disk_free_gb,
        disk_used_pct=metrics.disk_used_pct,
        docker_available=metrics.docker_available,
        running_workspaces=metrics.running_workspaces,
        allocated_cpu_cores=metrics.allocated_cpu_cores,
        allocated_ram_mb=metrics.allocated_ram_mb,
        admission=[
            AdmissionStatusPublic(
                workspace_class=item.workspace_class,
                allowed=item.allowed,
                severity=item.severity,
                reason=item.reason,
            )
            for item in decisions
        ],
    )


@system_router.get("/backups/config", response_model=BackupConfigPublic)
async def get_backup_config(
    _: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> BackupConfigPublic:
    """Return encrypted restic backup configuration (secrets masked)."""
    config = await get_or_create_backup_config(db)
    await db.commit()
    return _serialize_backup_config(config)


@system_router.patch("/backups/config", response_model=BackupConfigPublic)
async def update_backup_config(
    payload: BackupConfigUpdateRequest,
    request: Request,
    admin: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> BackupConfigPublic:
    """Update encrypted restic backup repository, credentials and retention."""
    config = await get_or_create_backup_config(db)
    next_provider = cast(BackupProvider, payload.provider or config.provider)
    next_repo = payload.repository if payload.repository is not None else config.repository

    try:
        validated_repo = validate_backup_repository(next_provider, next_repo)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if payload.enabled is not None:
        config.enabled = payload.enabled
    config.provider = next_provider
    config.repository = validated_repo
    if payload.schedule_cron is not None:
        config.schedule_cron = payload.schedule_cron.strip()
    if payload.retention_daily is not None:
        config.retention_daily = payload.retention_daily
    if payload.retention_weekly is not None:
        config.retention_weekly = payload.retention_weekly
    if payload.password is not None:
        config.encrypted_password = encrypt_secret(payload.password)
    if payload.s3_access_key is not None:
        config.encrypted_s3_access_key = (
            encrypt_secret(payload.s3_access_key.strip())
            if payload.s3_access_key.strip()
            else None
        )
    if payload.s3_secret_key is not None:
        config.encrypted_s3_secret_key = (
            encrypt_secret(payload.s3_secret_key.strip())
            if payload.s3_secret_key.strip()
            else None
        )

    await record_audit_event(
        db,
        action="system.backup_config_updated",
        resource_type="backup_config",
        resource_id="1",
        actor=admin,
        ip_address=get_client_ip(request),
        details={"provider": config.provider, "enabled": config.enabled},
    )
    await db.commit()
    await db.refresh(config)
    return _serialize_backup_config(config)


@system_router.get("/backups/snapshots", response_model=list[BackupSnapshotPublic])
async def list_backup_snapshots(
    limit: int = Query(default=25, ge=1, le=100),
    _: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> list[BackupSnapshot]:
    """List recent restic backup snapshot runs."""
    rows = (
        await db.execute(
            select(BackupSnapshot)
            .order_by(desc(BackupSnapshot.started_at))
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


@system_router.post("/backups/run", response_model=BackupSnapshotPublic)
async def trigger_manual_backup(
    request: Request,
    admin: User = Depends(require_instance_admin),
    db: AsyncSession = Depends(get_db),
) -> BackupSnapshot:
    """Trigger an immediate restic backup snapshot and record execution result."""
    config = await get_or_create_backup_config(db)
    snapshot = await run_restic_backup(db, config, trigger="manual")
    await record_audit_event(
        db,
        action="system.backup_triggered",
        resource_type="backup_snapshot",
        resource_id=str(snapshot.id),
        actor=admin,
        ip_address=get_client_ip(request),
        details={"status": snapshot.status, "repository": snapshot.repository},
    )
    await db.commit()
    return snapshot
