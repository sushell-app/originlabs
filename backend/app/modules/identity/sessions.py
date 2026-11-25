"""Redis-backed user sessions, HTTP-only cookies and rate limiting."""

from datetime import UTC, datetime
import json
import uuid

from fastapi import Response

from app.core.config import get_settings
from app.core.redis import get_redis
from app.modules.identity.security import generate_opaque_token, hash_token


def _session_key(raw_token: str) -> str:
    return f"session:{hash_token(raw_token)}"


async def create_session(user_id: uuid.UUID) -> str:
    """Create a new Redis session and return the opaque raw token."""
    settings = get_settings()
    raw_token = generate_opaque_token()
    payload = json.dumps(
        {
            "user_id": str(user_id),
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    client = get_redis()
    try:
        await client.set(_session_key(raw_token), payload, ex=settings.session_ttl_seconds)
    finally:
        await client.aclose()
    return raw_token


async def resolve_session_user_id(raw_token: str) -> uuid.UUID | None:
    """Resolve the authenticated user UUID from a raw session cookie token."""
    if not raw_token:
        return None
    client = get_redis()
    try:
        raw_payload = await client.get(_session_key(raw_token))
    finally:
        await client.aclose()

    if not raw_payload:
        return None
    try:
        data = json.loads(raw_payload)
        return uuid.UUID(data["user_id"])
    except (ValueError, KeyError, TypeError):
        return None


async def revoke_session(raw_token: str) -> None:
    """Delete an active session from Redis."""
    if not raw_token:
        return
    client = get_redis()
    try:
        await client.delete(_session_key(raw_token))
    finally:
        await client.aclose()


def set_session_cookie(response: Response, raw_token: str) -> None:
    """Attach the HTTP-only session cookie to an HTTP response."""
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        domain=settings.cookie_domain,
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie from the browser."""
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain,
        path="/",
    )


async def enforce_rate_limit(
    scope: str,
    key: str,
    *,
    max_attempts: int,
    window_seconds: int,
) -> bool:
    """Increment a sliding counter in Redis; return True if within allowed limit."""
    redis_key = f"ratelimit:{scope}:{key}"
    client = get_redis()
    try:
        count = await client.incr(redis_key)
        if count == 1:
            await client.expire(redis_key, window_seconds)
        return bool(count <= max_attempts)
    finally:
        await client.aclose()
