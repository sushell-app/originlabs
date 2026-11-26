"""Collaboration tables: knowledge base, team chat and tasks.

Revision ID: 0004_collab_tables
Revises: 0003_system_updates
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_collab_tables"
down_revision: str | Sequence[str] | None = "0003_system_updates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_folders",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("parent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["knowledge_folders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_folders_organization_id",
        "knowledge_folders",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_folders_parent_id",
        "knowledge_folders",
        ["parent_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_docs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("folder_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("author_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["folder_id"], ["knowledge_folders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_docs_folder_id",
        "knowledge_docs",
        ["folder_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_docs_organization_id",
        "knowledge_docs",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "team_channels",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_team_channel_org_slug"),
    )
    op.create_index(
        "ix_team_channels_organization_id",
        "team_channels",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "team_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("channel_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("sender_name", sa.String(length=120), nullable=False),
        sa.Column("sender_email", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_private_note", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["team_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_messages_channel_id", "team_messages", ["channel_id"], unique=False)
    op.create_index("ix_team_messages_created_at", "team_messages", ["created_at"], unique=False)

    op.create_table(
        "team_tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source_message_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("assignee_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_message_id"], ["team_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_team_tasks_organization_id",
        "team_tasks",
        ["organization_id"],
        unique=False,
    )
    op.create_index("ix_team_tasks_status", "team_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_team_tasks_status", table_name="team_tasks")
    op.drop_index("ix_team_tasks_organization_id", table_name="team_tasks")
    op.drop_table("team_tasks")

    op.drop_index("ix_team_messages_created_at", table_name="team_messages")
    op.drop_index("ix_team_messages_channel_id", table_name="team_messages")
    op.drop_table("team_messages")

    op.drop_index("ix_team_channels_organization_id", table_name="team_channels")
    op.drop_table("team_channels")

    op.drop_index("ix_knowledge_docs_organization_id", table_name="knowledge_docs")
    op.drop_index("ix_knowledge_docs_folder_id", table_name="knowledge_docs")
    op.drop_table("knowledge_docs")

    op.drop_index("ix_knowledge_folders_parent_id", table_name="knowledge_folders")
    op.drop_index("ix_knowledge_folders_organization_id", table_name="knowledge_folders")
    op.drop_table("knowledge_folders")
