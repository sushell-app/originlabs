"""Pydantic v2 schemas for System updates, notifications, host metrics and backups."""

import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.system.backups import validate_backup_repository

ReleaseChannel = Literal["stable", "beta"]
BackupProvider = Literal["local", "s3"]


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


class AdmissionStatusPublic(BaseModel):
    """Admission control verdict for a workspace class."""

    workspace_class: Literal["light", "standard", "heavy"]
    allowed: bool
    severity: str
    reason: str


class HostMetricsResponse(BaseModel):
    """Live server telemetry and workspace admission matrix."""

    hostname: str
    os_name: str
    arch: str
    cpu_cores: int
    load_avg_1m: float
    ram_total_mb: int
    ram_available_mb: int
    ram_used_pct: float
    disk_total_gb: float
    disk_free_gb: float
    disk_used_pct: float
    docker_available: bool
    running_workspaces: int
    allocated_cpu_cores: float
    allocated_ram_mb: int
    admission: list[AdmissionStatusPublic]


class BackupConfigPublic(BaseModel):
    """Encrypted restic backup configuration without exposing secrets."""

    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    provider: BackupProvider
    repository: str
    schedule_cron: str
    retention_daily: int
    retention_weekly: int
    has_password: bool
    has_s3_credentials: bool
    last_backup_at: datetime | None
    updated_at: datetime


class BackupConfigUpdateRequest(BaseModel):
    """Update encrypted restic backup repository and retention settings."""

    enabled: bool | None = None
    provider: BackupProvider | None = None
    repository: str | None = Field(default=None, max_length=500)
    schedule_cron: str | None = Field(default=None, min_length=9, max_length=64)
    retention_daily: int | None = Field(default=None, ge=1, le=90)
    retention_weekly: int | None = Field(default=None, ge=1, le=52)
    password: str | None = Field(default=None, min_length=8, max_length=256)
    s3_access_key: str | None = Field(default=None, max_length=256)
    s3_secret_key: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_repo_with_provider(self) -> "BackupConfigUpdateRequest":
        if self.repository is not None and self.provider is not None:
            self.repository = validate_backup_repository(self.provider, self.repository)
        return self


class BackupSnapshotPublic(BaseModel):
    """Serialized restic backup execution record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    trigger: str
    repository: str
    snapshot_id: str | None
    summary: str
    started_at: datetime
    completed_at: datetime | None
