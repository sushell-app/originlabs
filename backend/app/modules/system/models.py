"""SQLAlchemy ORM models for System notifications, updates and encrypted restic backups."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SystemNotification(Base):
    """Administrator-facing notification persisted in PostgreSQL."""

    __tablename__ = "system_notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(32), default="update", nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target_version: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    release_notes_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )


class InstanceUpdateState(Base):
    """Singleton state storing update channel, latest release info and webhook config."""

    __tablename__ = "instance_update_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    channel: Mapped[str] = mapped_column(String(16), default="stable", nullable=False)
    auto_check_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_available_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latest_release_notes_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latest_changelog: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    webhook_encrypted_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class BackupConfig(Base):
    """Singleton encrypted restic backup configuration."""

    __tablename__ = "backup_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), default="local", nullable=False)
    repository: Mapped[str] = mapped_column(
        String(500), default="/var/backups/originlabs", nullable=False
    )
    schedule_cron: Mapped[str] = mapped_column(String(64), default="0 3 * * *", nullable=False)
    retention_daily: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    retention_weekly: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    encrypted_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_s3_access_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_s3_secret_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_backup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class BackupSnapshot(Base):
    """Execution history log for restic backup snapshots."""

    __tablename__ = "backup_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True, nullable=False)
    trigger: Mapped[str] = mapped_column(String(24), default="manual", nullable=False)
    repository: Mapped[str] = mapped_column(String(500), nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
