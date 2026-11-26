"""Pydantic v2 schemas for Workspaces lifecycle and resource classes."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WORKSPACE_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"

WorkspaceClass = Literal["light", "standard", "heavy"]
WorkspaceStatus = Literal["stopped", "starting", "running", "stopping", "error"]


class WorkspaceCreateRequest(BaseModel):
    """Create a containerized code-server workspace for a project."""

    project_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=WORKSPACE_SLUG_PATTERN)
    workspace_class: WorkspaceClass = "standard"
    idle_timeout_minutes: int = Field(default=60, ge=10, le=1440)
    auto_start: bool = False


class WorkspacePublic(BaseModel):
    """Serialized workspace record enriched with computed IDE URL."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str
    slug: str
    workspace_class: WorkspaceClass
    image: str
    status: WorkspaceStatus
    container_id: str | None
    container_name: str
    volume_name: str
    subdomain: str
    ide_url: str
    idle_timeout_minutes: int
    last_activity_at: datetime | None
    started_at: datetime | None
    stopped_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
