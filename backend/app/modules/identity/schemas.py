"""Pydantic v2 schemas for Identity endpoints."""

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"

OrgRole = Literal["owner", "admin", "developer", "viewer"]
InviteRole = Literal["admin", "developer", "viewer"]


class SetupStatusResponse(BaseModel):
    """Whether initial instance admin setup is still required."""

    setup_required: bool
    bootstrap_token_required: bool


class SetupRequest(BaseModel):
    """Payload to create the initial instance administrator and first organization."""

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    organization_name: str = Field(min_length=2, max_length=120)
    organization_slug: str = Field(pattern=SLUG_PATTERN)
    bootstrap_token: str | None = Field(default=None, max_length=256)


class LoginRequest(BaseModel):
    """Email/password authentication payload."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    """Public user profile returned to authenticated sessions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_instance_admin: bool
    is_active: bool
    created_at: datetime


class OrganizationWithRole(BaseModel):
    """Organization summary enriched with the current user's role."""

    id: uuid.UUID
    name: str
    slug: str
    role: OrgRole
    created_at: datetime


class AuthSessionResponse(BaseModel):
    """Authenticated user profile and accessible organizations."""

    user: UserPublic
    organizations: list[OrganizationWithRole]


class CreateOrganizationRequest(BaseModel):
    """Create a new organization."""

    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=SLUG_PATTERN)


class OrganizationMemberPublic(BaseModel):
    """Serialized organization member."""

    id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: OrgRole
    is_instance_admin: bool
    created_at: datetime


class CreateInvitationRequest(BaseModel):
    """Invite a user email into an organization with a role."""

    email: EmailStr
    role: InviteRole = "developer"


class InvitationPublic(BaseModel):
    """Pending or accepted invitation metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    role: InviteRole
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationCreatedResponse(BaseModel):
    """Invitation creation response containing the one-time invite link token."""

    invitation: InvitationPublic
    invite_token: str
    invite_path: str


class AcceptInvitationRequest(BaseModel):
    """Accept an organization invitation and establish an active session."""

    token: str = Field(min_length=16, max_length=256)
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class UpdateMemberRoleRequest(BaseModel):
    """Update an existing organization member's role."""

    role: OrgRole
