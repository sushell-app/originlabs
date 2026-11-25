"""ARQ background worker for async Docker, Git, restic and update-check jobs."""

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.modules.system.updates import check_for_updates, get_or_create_update_state


async def ping_worker(ctx: dict[str, Any], source: str = "system") -> dict[str, str]:
    """Sanity-check background job used to verify Redis worker execution."""
    _ = ctx
    return {"status": "ok", "source": source}


async def check_updates_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Periodic job checking signed releases and creating admin notifications."""
    _ = ctx
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


class WorkerSettings:
    """ARQ worker configuration loaded from REDIS_URL."""

    functions = [ping_worker, check_updates_job]
    cron_jobs = [cron(check_updates_job, hour={0, 6, 12, 18}, minute=15)]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
