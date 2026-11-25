"""Identity API routers: setup, auth, organizations, invitations, RBAC and forward_auth."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.audit.service import record_audit_event
from app.modules.identity.dependencies import assert_org_access, get_client_ip, get_current_user
from app.modules.identity.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    User,
)
from app.modules.identity.schemas import (
    AcceptInvitationRequest,
    AuthSessionResponse,
    CreateInvitationRequest,
    CreateOrganizationRequest,
    InvitationCreatedResponse,
    InvitationPublic,
    InviteRole,
    LoginRequest,
    OrganizationMemberPublic,
    OrganizationWithRole,
    OrgRole,
    SetupRequest,
    SetupStatusResponse,
    UpdateMemberRoleRequest,
    UserPublic,
)
from app.modules.identity.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_bootstrap_token,
    verify_password,
)
from app.modules.identity.sessions import (
    clear_session_cookie,
    create_session,
    enforce_rate_limit,
    resolve_session_user_id,
    revoke_session,
    set_session_cookie,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
orgs_router = APIRouter(prefix="/organizations", tags=["organizations"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

INVITATION_TTL_HOURS = 72


async def _load_user_organizations(
    db: AsyncSession,
    user: User,
) -> list[OrganizationWithRole]:
    """Load organizations accessible to the user along with their effective role."""
    stmt = (
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        OrganizationWithRole(
            id=org.id,
            name=org.name,
            slug=org.slug,
            role=cast(OrgRole, role),
            created_at=org.created_at,
        )
        for org, role in rows
    ]


async def _count_org_owners(db: AsyncSession, organization_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(OrganizationMember.id)).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == "owner",
        )
    )
    return int(result.scalar_one() or 0)


@auth_router.get("/setup-status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db)) -> SetupStatusResponse:
    """Return whether initial instance setup is required."""
    settings = get_settings()
    exists = (await db.execute(select(User.id).limit(1))).scalar_one_or_none()
    return SetupStatusResponse(
        setup_required=exists is None,
        bootstrap_token_required=bool(settings.originlabs_bootstrap_token),
    )


@auth_router.post("/setup", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def initial_setup(
    payload: SetupRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    """Create the initial instance administrator and first organization (one-time)."""
    settings = get_settings()
    ip_addr = get_client_ip(request)

    allowed = await enforce_rate_limit(
        "setup",
        ip_addr or "unknown",
        max_attempts=10,
        window_seconds=300,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de configuración inicial. Espera unos minutos.",
        )

    existing_user = (await db.execute(select(User.id).limit(1))).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La instancia ya fue configurada inicialmente.",
        )

    if not verify_bootstrap_token(payload.bootstrap_token, settings.originlabs_bootstrap_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de bootstrap inválido.",
        )

    normalized_email = payload.email.strip().lower()
    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        is_instance_admin=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    org = Organization(
        name=payload.organization_name.strip(),
        slug=payload.organization_slug.strip().lower(),
        created_by_id=user.id,
    )
    db.add(org)
    await db.flush()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)

    await record_audit_event(
        db,
        action="auth.setup",
        resource_type="instance",
        resource_id=str(org.id),
        actor=user,
        organization_id=org.id,
        ip_address=ip_addr,
        details={"organization_slug": org.slug},
    )
    await db.commit()
    await db.refresh(user)

    raw_token = await create_session(user.id)
    set_session_cookie(response, raw_token)
    orgs = await _load_user_organizations(db, user)
    return AuthSessionResponse(user=UserPublic.model_validate(user), organizations=orgs)


@auth_router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    """Authenticate a user with email and password and set HTTP-only session cookie."""
    normalized_email = payload.email.strip().lower()
    ip_addr = get_client_ip(request)
    rate_key = f"{ip_addr or 'unknown'}:{normalized_email}"

    allowed = await enforce_rate_limit(
        "login",
        rate_key,
        max_attempts=10,
        window_seconds=300,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión. Intenta más tarde.",
        )

    user = (
        await db.execute(select(User).where(User.email == normalized_email))
    ).scalar_one_or_none()

    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        await record_audit_event(
            db,
            action="auth.login_failed",
            resource_type="user",
            actor_email=normalized_email,
            ip_address=ip_addr,
            details={"reason": "invalid_credentials_or_inactive"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )

    await record_audit_event(
        db,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        actor=user,
        ip_address=ip_addr,
    )
    await db.commit()

    raw_token = await create_session(user.id)
    set_session_cookie(response, raw_token)
    orgs = await _load_user_organizations(db, user)
    return AuthSessionResponse(user=UserPublic.model_validate(user), organizations=orgs)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the active Redis session and clear the browser cookie."""
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        user_id = await resolve_session_user_id(raw_token)
        if user_id is not None:
            user = (
                await db.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            await record_audit_event(
                db,
                action="auth.logout",
                resource_type="user",
                resource_id=str(user_id),
                actor=user,
                ip_address=get_client_ip(request),
            )
            await db.commit()
        await revoke_session(raw_token)
    clear_session_cookie(response)


@auth_router.get("/me", response_model=AuthSessionResponse)
async def auth_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    """Return the authenticated user's profile and organization memberships."""
    orgs = await _load_user_organizations(db, user)
    return AuthSessionResponse(user=UserPublic.model_validate(user), organizations=orgs)


@auth_router.get("/oidc/providers")
async def list_oidc_providers() -> dict[str, list[dict[str, str]]]:
    """Return configured OIDC providers (reserved for OIDC integration)."""
    return {"providers": []}


@auth_router.post("/invitations/accept", response_model=AuthSessionResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    """Accept an organization invitation, create or verify user account, and sign in."""
    ip_addr = get_client_ip(request)
    token_digest = hash_token(payload.token.strip())
    invitation = (
        await db.execute(
            select(OrganizationInvitation).where(
                OrganizationInvitation.token_hash == token_digest
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La invitación es inválida, ya fue usada o expiró.",
        )

    user = (
        await db.execute(select(User).where(User.email == invitation.email))
    ).scalar_one_or_none()

    if user is None:
        if not payload.full_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Debes indicar tu nombre completo para crear tu cuenta.",
            )
        user = User(
            email=invitation.email,
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
            is_instance_admin=False,
            is_active=True,
        )
        db.add(user)
        await db.flush()
    else:
        if not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Esta dirección ya tiene cuenta; introduce tu contraseña actual para aceptar."
                ),
            )

    existing_member = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == invitation.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()

    if existing_member is None:
        db.add(
            OrganizationMember(
                organization_id=invitation.organization_id,
                user_id=user.id,
                role=invitation.role,
            )
        )

    invitation.accepted_at = now
    await record_audit_event(
        db,
        action="org.member_joined",
        resource_type="organization_member",
        resource_id=str(user.id),
        actor=user,
        organization_id=invitation.organization_id,
        ip_address=ip_addr,
        details={"role": invitation.role},
    )
    await db.commit()
    await db.refresh(user)

    raw_token = await create_session(user.id)
    set_session_cookie(response, raw_token)
    orgs = await _load_user_organizations(db, user)
    return AuthSessionResponse(user=UserPublic.model_validate(user), organizations=orgs)


@orgs_router.get("", response_model=list[OrganizationWithRole])
async def list_organizations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationWithRole]:
    """List organizations the current user belongs to (or all for instance admins)."""
    if not user.is_instance_admin:
        return await _load_user_organizations(db, user)

    orgs = (
        await db.execute(select(Organization).order_by(Organization.created_at.asc()))
    ).scalars().all()
    memberships = (
        await db.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == user.id)
        )
    ).scalars().all()
    role_by_org = {m.organization_id: m.role for m in memberships}
    return [
        OrganizationWithRole(
            id=org.id,
            name=org.name,
            slug=org.slug,
            role=cast(OrgRole, role_by_org.get(org.id, "owner")),
            created_at=org.created_at,
        )
        for org in orgs
    ]


@orgs_router.post("", response_model=OrganizationWithRole, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrganizationRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationWithRole:
    """Create a new organization and assign the creator as owner."""
    slug = payload.slug.strip().lower()
    existing = (
        await db.execute(select(Organization.id).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una organización con ese slug.",
        )

    org = Organization(
        name=payload.name.strip(),
        slug=slug,
        created_by_id=user.id,
    )
    db.add(org)
    await db.flush()

    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
    )
    await record_audit_event(
        db,
        action="org.created",
        resource_type="organization",
        resource_id=str(org.id),
        actor=user,
        organization_id=org.id,
        ip_address=get_client_ip(request),
        details={"slug": org.slug},
    )
    await db.commit()
    await db.refresh(org)

    return OrganizationWithRole(
        id=org.id,
        name=org.name,
        slug=org.slug,
        role="owner",
        created_at=org.created_at,
    )


@orgs_router.get("/{organization_id}/members", response_model=list[OrganizationMemberPublic])
async def list_organization_members(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationMemberPublic]:
    """List all members of an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    rows = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.created_at.asc())
        )
    ).all()
    return [
        OrganizationMemberPublic(
            id=member.id,
            user_id=member_user.id,
            email=member_user.email,
            full_name=member_user.full_name,
            role=cast(OrgRole, member.role),
            is_instance_admin=member_user.is_instance_admin,
            created_at=member.created_at,
        )
        for member, member_user in rows
    ]


@orgs_router.get("/{organization_id}/invitations", response_model=list[InvitationPublic])
async def list_organization_invitations(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationPublic]:
    """List pending invitations for an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin"})
    now = datetime.now(UTC)
    invitations = (
        await db.execute(
            select(OrganizationInvitation)
            .where(
                OrganizationInvitation.organization_id == organization_id,
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.expires_at > now,
            )
            .order_by(OrganizationInvitation.created_at.desc())
        )
    ).scalars().all()
    return [
        InvitationPublic(
            id=inv.id,
            organization_id=inv.organization_id,
            email=inv.email,
            role=cast(InviteRole, inv.role),
            expires_at=inv.expires_at,
            accepted_at=inv.accepted_at,
            created_at=inv.created_at,
        )
        for inv in invitations
    ]


@orgs_router.post(
    "/{organization_id}/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_invitation(
    organization_id: uuid.UUID,
    payload: CreateInvitationRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationCreatedResponse:
    """Create a 72h invitation link token for an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin"})
    normalized_email = payload.email.strip().lower()

    already_member = (
        await db.execute(
            select(OrganizationMember.id)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == organization_id,
                User.email == normalized_email,
            )
        )
    ).scalar_one_or_none()
    if already_member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese usuario ya pertenece a la organización.",
        )

    raw_token = generate_opaque_token()
    invitation = OrganizationInvitation(
        organization_id=organization_id,
        email=normalized_email,
        role=payload.role,
        token_hash=hash_token(raw_token),
        invited_by_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=INVITATION_TTL_HOURS),
    )
    db.add(invitation)
    await db.flush()

    await record_audit_event(
        db,
        action="org.member_invited",
        resource_type="organization_invitation",
        resource_id=str(invitation.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"invited_email": normalized_email, "role": payload.role},
    )
    await db.commit()
    await db.refresh(invitation)

    return InvitationCreatedResponse(
        invitation=InvitationPublic(
            id=invitation.id,
            organization_id=invitation.organization_id,
            email=invitation.email,
            role=cast(InviteRole, invitation.role),
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            created_at=invitation.created_at,
        ),
        invite_token=raw_token,
        invite_path=f"/?invite={raw_token}",
    )


@orgs_router.patch(
    "/{organization_id}/members/{member_id}",
    response_model=OrganizationMemberPublic,
)
async def update_member_role(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMemberPublic:
    """Update an organization member's role while protecting the last owner."""
    await assert_org_access(db, user, organization_id, {"owner", "admin"})
    row = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == organization_id,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")

    member, member_user = row
    if (
        member.role == "owner"
        and payload.role != "owner"
        and await _count_org_owners(db, organization_id) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes degradar al último owner de la organización.",
        )

    previous_role = member.role
    member.role = payload.role
    await record_audit_event(
        db,
        action="org.member_role_updated",
        resource_type="organization_member",
        resource_id=str(member.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={
            "target_email": member_user.email,
            "previous_role": previous_role,
            "new_role": payload.role,
        },
    )
    await db.commit()
    await db.refresh(member)

    return OrganizationMemberPublic(
        id=member.id,
        user_id=member_user.id,
        email=member_user.email,
        full_name=member_user.full_name,
        role=cast(OrgRole, member.role),
        is_instance_admin=member_user.is_instance_admin,
        created_at=member.created_at,
    )


@orgs_router.delete(
    "/{organization_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a member from an organization while protecting the last owner."""
    await assert_org_access(db, user, organization_id, {"owner", "admin"})
    row = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == organization_id,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")

    member, member_user = row
    if member.role == "owner" and await _count_org_owners(db, organization_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar al último owner de la organización.",
        )

    await record_audit_event(
        db,
        action="org.member_removed",
        resource_type="organization_member",
        resource_id=str(member.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"removed_email": member_user.email, "role": member.role},
    )
    await db.delete(member)
    await db.commit()


@internal_router.get("/forward-auth", status_code=status.HTTP_200_OK)
async def caddy_forward_auth(
    response: Response,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Validate browser session for Caddy forward_auth before proxying to workspaces."""
    response.headers["X-OriginLabs-User-Id"] = str(user.id)
    response.headers["X-OriginLabs-User-Email"] = user.email
    response.headers["X-OriginLabs-Is-Admin"] = "true" if user.is_instance_admin else "false"
    return {"status": "authorized"}
