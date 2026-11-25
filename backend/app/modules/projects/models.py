"""SQLAlchemy ORM models for Projects, Git connections, members and encrypted env vars."""

from datetime import UTC, datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GitConnection(Base):
    """Git provider credential (GitHub, GitLab or headless OriginLabs Git) scoped to an org."""

    __tablename__ = "git_connections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    account_login: Mapped[str | None] = mapped_column(String(120), nullable=True)
    encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="git_connection")


class Project(Base):
    """Development project linking a repository, team members and default workspace settings."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    git_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("git_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    git_provider: Mapped[str] = mapped_column(String(32), default="github", nullable=False)
    repo_full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repo_clone_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(120), default="main", nullable=False)
    default_workspace_class: Mapped[str] = mapped_column(
        String(32), default="standard", nullable=False
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    git_connection: Mapped[GitConnection | None] = relationship(back_populates="projects")
    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    env_vars: Mapped[list["ProjectEnvVar"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(Base):
    """Per-project team assignment and role."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), default="developer", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="members")


class ProjectEnvVar(Base):
    """Encrypted environment variable injected into project workspaces."""

    __tablename__ = "project_env_vars"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_project_env_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="env_vars")
