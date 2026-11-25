"""Pydantic v2 schemas with strict sanitization for Projects and Git connectors."""

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROJECT_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"
BRANCH_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$"
ENV_KEY_PATTERN = r"^[A-Z_][A-Z0-9_]{0,119}$"

GitProviderType = Literal["github", "gitlab", "internal"]
WorkspaceClassType = Literal["light", "standard", "heavy"]
ProjectRole = Literal["maintainer", "developer", "viewer"]


def _validate_https_repo_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if any(ch.isspace() or ord(ch) < 32 for ch in cleaned):
        raise ValueError("La URL del repositorio contiene caracteres inválidos.")
    parsed = urlparse(cleaned)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Solo se permiten URLs de repositorio https:// válidas.")
    if "@" in parsed.netloc:
        raise ValueError("No incrustes credenciales en la URL del repositorio.")
    return cleaned


def _validate_branch_name(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("-") or ".." in cleaned or "//" in cleaned:
        raise ValueError("Nombre de rama inválido.")
    return cleaned


def _validate_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().rstrip("/")
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("URL base del proveedor inválida.")
    if "@" in parsed.netloc:
        raise ValueError("La URL base no debe incluir credenciales.")
    return cleaned


class GitConnectionCreateRequest(BaseModel):
    """Create a Git provider connection for an organization."""

    provider: GitProviderType
    name: str = Field(min_length=2, max_length=120)
    base_url: str | None = Field(default=None, max_length=255)
    access_token: str | None = Field(default=None, min_length=6, max_length=512)
    verify: bool = True

    @field_validator("base_url")
    @classmethod
    def check_base_url(cls, value: str | None) -> str | None:
        return _validate_base_url(value)


class GitConnectionPublic(BaseModel):
    """Serialized Git connection without exposing stored secrets."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    provider: GitProviderType
    name: str
    base_url: str
    account_login: str | None
    has_token: bool
    created_at: datetime


class GitRepoSummaryPublic(BaseModel):
    """Normalized repository item returned when browsing a Git connection."""

    full_name: str
    clone_url: str
    default_branch: str
    private: bool
    provider: GitProviderType


class ProjectCreateRequest(BaseModel):
    """Create a project inside an organization."""

    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=PROJECT_SLUG_PATTERN)
    description: str = Field(default="", max_length=500)
    git_connection_id: uuid.UUID | None = None
    git_provider: GitProviderType = "github"
    repo_full_name: str | None = Field(default=None, max_length=255)
    repo_clone_url: str | None = Field(default=None, max_length=500)
    default_branch: str = Field(default="main", pattern=BRANCH_PATTERN)
    default_workspace_class: WorkspaceClassType = "standard"

    @field_validator("repo_clone_url")
    @classmethod
    def check_repo_url(cls, value: str | None) -> str | None:
        return _validate_https_repo_url(value)

    @field_validator("default_branch")
    @classmethod
    def check_branch(cls, value: str) -> str:
        return _validate_branch_name(value)


class ProjectUpdateRequest(BaseModel):
    """Update project metadata or default repository settings."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    git_connection_id: uuid.UUID | None = None
    git_provider: GitProviderType | None = None
    repo_full_name: str | None = Field(default=None, max_length=255)
    repo_clone_url: str | None = Field(default=None, max_length=500)
    default_branch: str | None = Field(default=None, pattern=BRANCH_PATTERN)
    default_workspace_class: WorkspaceClassType | None = None

    @field_validator("repo_clone_url")
    @classmethod
    def check_repo_url(cls, value: str | None) -> str | None:
        return _validate_https_repo_url(value)

    @field_validator("default_branch")
    @classmethod
    def check_branch(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_branch_name(value)


class ProjectPublic(BaseModel):
    """Serialized project record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str
    git_connection_id: uuid.UUID | None
    git_provider: GitProviderType
    repo_full_name: str | None
    repo_clone_url: str | None
    default_branch: str
    default_workspace_class: WorkspaceClassType
    created_at: datetime
    updated_at: datetime


class ProjectMemberAssignRequest(BaseModel):
    """Assign or update an organization user's role inside a project."""

    user_id: uuid.UUID
    role: ProjectRole = "developer"


class ProjectMemberPublic(BaseModel):
    """Serialized project team member."""

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role: ProjectRole
    created_at: datetime


class ProjectEnvVarUpsertRequest(BaseModel):
    """Create or update an encrypted environment variable for a project."""

    key: str = Field(pattern=ENV_KEY_PATTERN)
    value: str = Field(min_length=1, max_length=8192)
    is_secret: bool = True


class ProjectEnvVarPublic(BaseModel):
    """Serialized environment variable with secret masking."""

    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    is_secret: bool
    value: str | None
    masked_value: str
    updated_at: datetime
