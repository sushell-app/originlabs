"""Projects, Git connections, project members and encrypted env vars.

Revision ID: 0002_projects_and_git
Revises: 0001_identity_and_audit
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_projects_and_git"
down_revision: str | Sequence[str] | None = "0001_identity_and_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "git_connections",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("account_login", sa.String(length=120), nullable=True),
        sa.Column("encrypted_token", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_git_connections_organization_id",
        "git_connections",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("git_connection_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("git_provider", sa.String(length=32), nullable=False),
        sa.Column("repo_full_name", sa.String(length=255), nullable=True),
        sa.Column("repo_clone_url", sa.String(length=500), nullable=True),
        sa.Column("default_branch", sa.String(length=120), nullable=False),
        sa.Column("default_workspace_class", sa.String(length=32), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["git_connection_id"], ["git_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"], unique=False)
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=False)

    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
    )
    op.create_index(
        "ix_project_members_project_id",
        "project_members",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_members_user_id",
        "project_members",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "project_env_vars",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key", name="uq_project_env_key"),
    )
    op.create_index(
        "ix_project_env_vars_project_id",
        "project_env_vars",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_env_vars_project_id", table_name="project_env_vars")
    op.drop_table("project_env_vars")

    op.drop_index("ix_project_members_user_id", table_name="project_members")
    op.drop_index("ix_project_members_project_id", table_name="project_members")
    op.drop_table("project_members")

    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_git_connections_organization_id", table_name="git_connections")
    op.drop_table("git_connections")
