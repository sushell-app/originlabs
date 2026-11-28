"""Pydantic v2 schemas for System updates, notifications, host metrics and backups."""

import uuid
from datetime import datetime
from typing import Any, Literal, Self
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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
    def validate_repo_with_provider(self) -> Self:
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


class UpdateApplyRequest(BaseModel):
    """Trigger 1-click self-update to a validated target version."""

    target_version: str | None = Field(default=None, max_length=64)


class UpdateApplyResponse(BaseModel):
    """Result of launching the detached Docker Compose self-updater."""

    accepted: bool
    from_version: str
    target_version: str
    target_image: str
    updater_container_id: str
    message: str


class SmtpConfigPublic(BaseModel):
    """Encrypted SMTP configuration with secret password masked."""

    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    host: str
    port: int
    username: str
    has_password: bool
    from_email: str
    from_name: str
    use_tls: bool
    use_ssl: bool
    notify_updates: bool
    last_test_at: datetime | None
    last_test_status: str | None
    last_test_error: str | None
    updated_at: datetime


class SmtpConfigUpdateRequest(BaseModel):
    """Update outbound SMTP server, TLS mode and credentials."""

    enabled: bool | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=512)
    from_email: EmailStr | None = None
    from_name: str | None = Field(default=None, max_length=120)
    use_tls: bool | None = None
    use_ssl: bool | None = None
    notify_updates: bool | None = None

    @model_validator(mode="after")
    def check_tls_mode(self) -> Self:
        if self.use_tls is True and self.use_ssl is True:
            raise ValueError("No puedes activar STARTTLS y SSL directo al mismo tiempo.")
        return self


class SmtpTestRequest(BaseModel):
    """Optional recipient email override when testing SMTP delivery."""

    to_email: EmailStr | None = None


class SmtpTestResponse(BaseModel):
    """Outcome of executing an immediate SMTP test message."""

    ok: bool
    detail: str
    sent_to: str
    tested_at: datetime
