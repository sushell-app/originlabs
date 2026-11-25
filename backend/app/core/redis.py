"""Async Redis client helper and connectivity health check."""

from redis.asyncio import Redis

from app.core.config import get_settings


def get_redis() -> Redis:
    """Create an async Redis client from configured REDIS_URL."""
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def check_redis_health() -> tuple[bool, str | None]:
    """Ping Redis to verify queue and cache availability."""
    client = get_redis()
    try:
        pong = await client.ping()
        return bool(pong), None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        await client.aclose()
