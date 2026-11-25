"""Pydantic v2 schemas for System updates and admin notifications."""

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

ReleaseChannel = Literal["stable", "beta"]


class UpdateStatusResponse(BaseModel):
    """Current version, configured update channel and latest release status."""

    current_version: str
    channel: ReleaseChannel
    auto_check_enabled: bool
    releases_feed_configured: bool
    update_available: bool
    latest_available_version: str | None
    latest_severity: str | None
    latest_release_notes_url: str | None
    latest_changelog: list[str]
    last_checked_at: datetime | None
    webhook_url: str | None
    has_webhook_secret: bool
    warning: str | None = None


class UpdateSettingsRequest(BaseModel):
    """Update release channel, automatic checks and optional webhook alerts."""

    channel: ReleaseChannel | None = None
    auto_check_enabled: bool | None = None
    webhook_url: str | None = Field(default=None, max_length=500)
    webhook_secret: str | None = Field(default=None, max_length=256)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return ""
        parsed = urlparse(cleaned)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("El webhook de notificaciones debe usar https:// válido.")
        if "@" in parsed.netloc:
            raise ValueError("La URL del webhook no debe contener credenciales.")
        return cleaned


class SystemNotificationPublic(BaseModel):
    """Serialized administrator notification."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    severity: str
    title: str
    message: str
    target_version: str | None
    release_notes_url: str | None
    details: dict[str, Any]
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationsListResponse(BaseModel):
    """Notification feed with unread counter."""

    unread_count: int
    items: list[SystemNotificationPublic]
