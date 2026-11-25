"""System notifications and instance update tracking tables.

Revision ID: 0003_system_notifications_and_updates
Revises: 0002_projects_and_git
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_system_notifications_and_updates"
down_revision: str | Sequence[str] | None = "0002_projects_and_git"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_notifications",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("target_version", sa.String(length=64), nullable=True),
        sa.Column("release_notes_url", sa.String(length=500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_notifications_created_at",
        "system_notifications",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_system_notifications_is_read",
        "system_notifications",
        ["is_read"],
        unique=False,
    )
    op.create_index(
        "ix_system_notifications_target_version",
        "system_notifications",
        ["target_version"],
        unique=False,
    )

    op.create_table(
        "instance_update_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("auto_check_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_available_version", sa.String(length=64), nullable=True),
        sa.Column("latest_severity", sa.String(length=20), nullable=True),
        sa.Column("latest_release_notes_url", sa.String(length=500), nullable=True),
        sa.Column("latest_changelog", sa.JSON(), nullable=False),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("webhook_encrypted_secret", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("instance_update_state")
    op.drop_index("ix_system_notifications_target_version", table_name="system_notifications")
    op.drop_index("ix_system_notifications_is_read", table_name="system_notifications")
    op.drop_index("ix_system_notifications_created_at", table_name="system_notifications")
    op.drop_table("system_notifications")
