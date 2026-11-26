"""ARQ background worker for async Docker idle-reaping, restic and update-check jobs."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.modules.audit.service import record_audit_event
from app.modules.system.updates import check_for_updates, get_or_create_update_state
from app.modules.workspaces.models import Workspace
from app.modules.workspaces.orchestrator import WorkspaceOrchestrator


async def ping_worker(ctx: dict[Any, Any], source: str = "system") -> dict[str, str]:
    """Sanity-check background job used to verify Redis worker execution."""
    _ = ctx
    return {"status": "ok", "source": source}


async def check_updates_job(ctx: dict[Any, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Periodic job checking signed releases and creating admin notifications."""
    _ = (ctx, _args, _kwargs)
    async with async_session_factory() as db:
        state = await get_or_create_update_state(db)
        if not state.auto_check_enabled:
            return {"skipped": True, "reason": "auto_check_disabled"}
        result = await check_for_updates(db)
        return {
            "skipped": False,
            "update_available": result.update_available,
            "latest_version": result.state.latest_available_version,
            "notified": result.new_notification_created,
        }


async def reap_idle_workspaces_job(
    ctx: dict[Any, Any],
    *_args: Any,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Stop idle running workspaces to reclaim host CPU and memory automatically."""
    _ = (ctx, _args, _kwargs)
    settings = get_settings()
    orchestrator = WorkspaceOrchestrator(caddy_admin_url=settings.caddy_admin_url)
    now = datetime.now(UTC)
    stopped_count = 0

    async with async_session_factory() as db:
        running = (
            await db.execute(select(Workspace).where(Workspace.status == "running"))
        ).scalars().all()
        for ws in running:
            last_seen = ws.last_activity_at or ws.started_at or ws.created_at
            if now - last_seen < timedelta(minutes=ws.idle_timeout_minutes):
                continue
            try:
                orchestrator.stop_container(ws.container_name)
            except RuntimeError:
                pass
            await orchestrator.remove_caddy_route(workspace_id=str(ws.id))
            ws.status = "stopped"
            ws.stopped_at = now
            await record_audit_event(
                db,
                action="workspace.auto_stopped",
                resource_type="workspace",
                resource_id=str(ws.id),
                organization_id=ws.organization_id,
                details={"slug": ws.slug, "idle_timeout_minutes": ws.idle_timeout_minutes},
            )
            stopped_count += 1
        await db.commit()

    return {"checked": len(running), "stopped": stopped_count}


class WorkerSettings:
    """ARQ worker configuration loaded from REDIS_URL."""

    functions = [ping_worker, check_updates_job, reap_idle_workspaces_job]
    cron_jobs = [
        cron(cast(Any, check_updates_job), hour={0, 6, 12, 18}, minute=15),
        cron(cast(Any, reap_idle_workspaces_job), minute={0, 10, 20, 30, 40, 50}),
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
