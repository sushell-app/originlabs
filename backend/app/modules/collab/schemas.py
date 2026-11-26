"""Pydantic v2 schemas for Knowledge Base, Team Chat and Tasks."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CHANNEL_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,40}[a-z0-9]$"

TaskStatus = Literal["pending", "in_progress", "completed", "rejected"]
TaskPriority = Literal["low", "medium", "high"]


def _normalize_tags(raw_tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags[:12]:
        item = tag.strip().lower()[:32]
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    return cleaned


class KnowledgeFolderCreateRequest(BaseModel):
    """Create a folder inside the organization knowledge base."""

    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=CHANNEL_SLUG_PATTERN)
    parent_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class KnowledgeFolderPublic(BaseModel):
    """Serialized knowledge folder."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    parent_id: uuid.UUID | None
    project_id: uuid.UUID | None
    name: str
    slug: str
    created_at: datetime


class KnowledgeDocCreateRequest(BaseModel):
    """Create a Markdown knowledge document."""

    title: str = Field(min_length=2, max_length=200)
    content: str = Field(default="", max_length=100_000)
    folder_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)
    is_favorite: bool = False

    @field_validator("tags")
    @classmethod
    def check_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tags(value)


class KnowledgeDocUpdateRequest(BaseModel):
    """Update a knowledge document."""

    title: str | None = Field(default=None, min_length=2, max_length=200)
    content: str | None = Field(default=None, max_length=100_000)
    folder_id: uuid.UUID | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None

    @field_validator("tags")
    @classmethod
    def check_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_tags(value)


class KnowledgeDocPublic(BaseModel):
    """Serialized knowledge document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    folder_id: uuid.UUID | None
    title: str
    content: str
    tags: list[str]
    is_favorite: bool
    author_email: str | None
    created_at: datetime
    updated_at: datetime


class TeamChannelCreateRequest(BaseModel):
    """Create a team chat channel."""

    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=CHANNEL_SLUG_PATTERN)
    description: str = Field(default="", max_length=300)
    project_id: uuid.UUID | None = None


class TeamChannelPublic(BaseModel):
    """Serialized team chat channel."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    slug: str
    description: str
    created_at: datetime


class TeamMessageCreateRequest(BaseModel):
    """Post a message or private note in a channel."""

    body: str = Field(min_length=1, max_length=4000)
    is_private_note: bool = False


class TeamMessagePublic(BaseModel):
    """Serialized team chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel_id: uuid.UUID
    sender_user_id: uuid.UUID | None
    sender_name: str
    sender_email: str
    body: str
    is_private_note: bool
    created_at: datetime


class TeamTaskCreateRequest(BaseModel):
    """Create an organization or project task."""

    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=4000)
    priority: TaskPriority = "medium"
    project_id: uuid.UUID | None = None
    source_message_id: uuid.UUID | None = None
    assignee_user_id: uuid.UUID | None = None


class TeamTaskUpdateRequest(BaseModel):
    """Update task status, priority, title or assignee."""

    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_user_id: uuid.UUID | None = None


class TeamTaskPublic(BaseModel):
    """Serialized team task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    source_message_id: uuid.UUID | None
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    assignee_user_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
