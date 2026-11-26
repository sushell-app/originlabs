"""Workspaces and encrypted restic backup tables.

Revision ID: 0005_workspaces_backups
Revises: 0004_collab_tables
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_workspaces_backups"
down_revision: str | Sequence[str] | None = "0004_collab_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("workspace_class", sa.String(length=32), nullable=False),
        sa.Column("image", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("container_name", sa.String(length=128), nullable=False),
        sa.Column("volume_name", sa.String(length=128), nullable=False),
        sa.Column("subdomain", sa.String(length=128), nullable=False),
        sa.Column("idle_timeout_minutes", sa.Integer(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("container_name"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),
        sa.UniqueConstraint("subdomain"),
        sa.UniqueConstraint("volume_name"),
    )
    op.create_index(
        "ix_workspaces_organization_id",
        "workspaces",
        ["organization_id"],
        unique=False,
    )
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"], unique=False)
    op.create_index("ix_workspaces_project_id", "workspaces", ["project_id"], unique=False)
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=False)
    op.create_index("ix_workspaces_status", "workspaces", ["status"], unique=False)

    op.create_table(
        "backup_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("repository", sa.String(length=500), nullable=False),
        sa.Column("schedule_cron", sa.String(length=64), nullable=False),
        sa.Column("retention_daily", sa.Integer(), nullable=False),
        sa.Column("retention_weekly", sa.Integer(), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=True),
        sa.Column("encrypted_s3_access_key", sa.Text(), nullable=True),
        sa.Column("encrypted_s3_secret_key", sa.Text(), nullable=True),
        sa.Column("last_backup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "backup_snapshots",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("trigger", sa.String(length=24), nullable=False),
        sa.Column("repository", sa.String(length=500), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backup_snapshots_started_at",
        "backup_snapshots",
        ["started_at"],
        unique=False,
    )
    op.create_index("ix_backup_snapshots_status", "backup_snapshots", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_backup_snapshots_status", table_name="backup_snapshots")
    op.drop_index("ix_backup_snapshots_started_at", table_name="backup_snapshots")
    op.drop_table("backup_snapshots")

    op.drop_table("backup_configs")

    op.drop_index("ix_workspaces_status", table_name="workspaces")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_index("ix_workspaces_project_id", table_name="workspaces")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_table("workspaces")
