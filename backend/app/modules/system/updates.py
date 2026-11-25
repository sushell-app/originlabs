"""Signed release manifest checking and administrator update notifications."""

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.modules.system.models import InstanceUpdateState, SystemNotification

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-.]?([0-9A-Za-z.-]+))?$")


@dataclass(frozen=True, slots=True)
class ReleaseCandidate:
    """Normalized release metadata parsed from releases.json or GitHub Releases."""

    version: str
    severity: str
    changelog: list[str]
    release_notes_url: str | None


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    """Outcome of executing an instance update check."""

    state: InstanceUpdateState
    update_available: bool
    new_notification_created: bool
    warning: str | None = None


def parse_semver(version: str) -> tuple[tuple[int, int, int], int, tuple[str, ...]]:
    """Parse semantic version string into comparable tuple (prerelease < final)."""
    cleaned = version.strip()
    match = _SEMVER_RE.match(cleaned)
    if not match:
        return ((0, 0, 0), 0, (cleaned,))

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    prerelease = match.group(4)
    if not prerelease:
        return ((major, minor, patch), 1, ())
    parts = tuple(prerelease.lower().split("."))
    return ((major, minor, patch), 0, parts)


def is_newer_version(current: str, candidate: str) -> bool:
    """Return True if candidate version is strictly newer than current version."""
    return parse_semver(candidate) > parse_semver(current)


def canonical_manifest_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize release manifest excluding signature for deterministic Ed25519 signing."""
    unsigned = {k: v for k, v in payload.items() if k != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def verify_manifest_signature(
    payload: dict[str, Any],
    signature_b64: str,
    public_key_b64: str,
) -> bool:
    """Verify Ed25519 signature of a releases.json manifest."""
    try:
        pub_bytes = base64.b64decode(public_key_b64.strip(), validate=True)
        sig_bytes = base64.b64decode(signature_b64.strip(), validate=True)
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub_key.verify(sig_bytes, canonical_manifest_bytes(payload))
        return True
    except (ValueError, InvalidSignature):
        return False


def _parse_manifest_payload(
    data: Any,
    *,
    channel: str,
    public_key_b64: str | None,
) -> ReleaseCandidate | None:
    if isinstance(data, dict) and "channels" in data:
        if public_key_b64:
            signature = data.get("signature")
            if not isinstance(signature, str) or not verify_manifest_signature(
                data, signature, public_key_b64
            ):
                raise ValueError("Firma Ed25519 del manifiesto releases.json inválida.")

        channels = data.get("channels")
        if not isinstance(channels, dict):
            return None
        entry = channels.get(channel)
        if not isinstance(entry, dict) or not entry.get("version"):
            return None

        raw_changelog = entry.get("changelog_summary")
        changelog = (
            [str(item) for item in raw_changelog]
            if isinstance(raw_changelog, list)
            else []
        )
        raw_severity = str(entry.get("severity") or "normal").lower()
        severity = "security" if raw_severity == "security" else "info"
        notes_url = entry.get("release_notes_url")
        return ReleaseCandidate(
            version=str(entry["version"]).lstrip("v"),
            severity=severity,
            changelog=changelog,
            release_notes_url=str(notes_url) if notes_url else None,
        )

    # Fallback compatible con GitHub Releases API (/releases o /releases/latest)
    releases: list[dict[str, Any]] = []
    if isinstance(data, list):
        releases = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict) and "tag_name" in data:
        releases = [data]

    for rel in releases:
        if rel.get("draft"):
            continue
        if channel == "stable" and rel.get("prerelease"):
            continue
        tag = str(rel.get("tag_name") or "").lstrip("v")
        if not tag:
            continue
        body = str(rel.get("body") or "").strip()
        summary = [line.strip("-* ") for line in body.splitlines() if line.strip()][:5]
        return ReleaseCandidate(
            version=tag,
            severity="info",
            changelog=summary,
            release_notes_url=str(rel["html_url"]) if rel.get("html_url") else None,
        )
    return None


async def fetch_release_for_channel(
    *,
    url: str,
    channel: str,
    public_key_b64: str | None,
) -> ReleaseCandidate | None:
    """Download release manifest or GitHub Releases metadata and extract channel candidate."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
    return _parse_manifest_payload(payload, channel=channel, public_key_b64=public_key_b64)


async def get_or_create_update_state(db: AsyncSession) -> InstanceUpdateState:
    """Load singleton InstanceUpdateState row, creating defaults if missing."""
    state = (
        await db.execute(select(InstanceUpdateState).where(InstanceUpdateState.id == 1))
    ).scalar_one_or_none()
    if state is None:
        settings = get_settings()
        state = InstanceUpdateState(
            id=1,
            channel=settings.originlabs_release_channel,
            auto_check_enabled=True,
            latest_changelog=[],
        )
        db.add(state)
        await db.flush()
    return state


async def _dispatch_update_webhook(
    state: InstanceUpdateState,
    notification: SystemNotification,
) -> None:
    """Send best-effort signed JSON webhook to external ops chat (Slack/Discord/n8n)."""
    if not state.webhook_url:
        return
    body = json.dumps(
        {
            "event": "originlabs.update_available",
            "severity": notification.severity,
            "target_version": notification.target_version,
            "title": notification.title,
            "message": notification.message,
            "release_notes_url": notification.release_notes_url,
            "created_at": notification.created_at.isoformat(),
        },
        separators=(",", ":"),
    ).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if state.webhook_encrypted_secret:
        secret = decrypt_secret(state.webhook_encrypted_secret)
        sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-OriginLabs-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            await client.post(state.webhook_url, content=body, headers=headers)
    except httpx.HTTPError:
        return


async def check_for_updates(db: AsyncSession) -> UpdateCheckResult:
    """Check configured release feed, persist state and notify instance admins if newer."""
    settings = get_settings()
    state = await get_or_create_update_state(db)
    now = datetime.now(UTC)
    state.last_checked_at = now

    if not settings.originlabs_releases_url:
        await db.commit()
        await db.refresh(state)
        return UpdateCheckResult(
            state=state,
            update_available=bool(
                state.latest_available_version
                and is_newer_version(settings.app_version, state.latest_available_version)
            ),
            new_notification_created=False,
            warning="ORIGINLABS_RELEASES_URL no configurada aún en el servidor.",
        )

    try:
        candidate = await fetch_release_for_channel(
            url=settings.originlabs_releases_url,
            channel=state.channel,
            public_key_b64=settings.originlabs_releases_public_key,
        )
    except (httpx.HTTPError, ValueError) as exc:
        await db.commit()
        await db.refresh(state)
        return UpdateCheckResult(
            state=state,
            update_available=bool(
                state.latest_available_version
                and is_newer_version(settings.app_version, state.latest_available_version)
            ),
            new_notification_created=False,
            warning=f"No se pudo verificar actualizaciones: {exc}",
        )

    if candidate is None:
        await db.commit()
        await db.refresh(state)
        return UpdateCheckResult(
            state=state,
            update_available=False,
            new_notification_created=False,
        )

    state.latest_available_version = candidate.version
    state.latest_severity = candidate.severity
    state.latest_release_notes_url = candidate.release_notes_url
    state.latest_changelog = candidate.changelog

    newer = is_newer_version(settings.app_version, candidate.version)
    created_notification: SystemNotification | None = None

    if newer:
        existing = (
            await db.execute(
                select(SystemNotification.id).where(
                    SystemNotification.category == "update",
                    SystemNotification.target_version == candidate.version,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            is_security = candidate.severity == "security"
            created_notification = SystemNotification(
                category="update",
                severity="security" if is_security else "info",
                title=(
                    f"Actualización de seguridad disponible: v{candidate.version}"
                    if is_security
                    else f"Nueva versión disponible: v{candidate.version}"
                ),
                message=(
                    f"La instancia ejecuta {settings.app_version} y hay una versión nueva "
                    f"({candidate.version}) en el canal {state.channel}."
                ),
                target_version=candidate.version,
                release_notes_url=candidate.release_notes_url,
                details={
                    "channel": state.channel,
                    "changelog": candidate.changelog,
                },
            )
            db.add(created_notification)

    await db.commit()
    await db.refresh(state)

    if created_notification is not None:
        await db.refresh(created_notification)
        await _dispatch_update_webhook(state, created_notification)

    return UpdateCheckResult(
        state=state,
        update_available=newer,
        new_notification_created=created_notification is not None,
    )
