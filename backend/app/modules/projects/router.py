"""API endpoints for Projects, Git connections, project members and encrypted env vars."""

from typing import cast
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.database import get_db
from app.modules.audit.service import record_audit_event
from app.modules.identity.dependencies import assert_org_access, get_client_ip, get_current_user
from app.modules.identity.models import OrganizationMember, User
from app.modules.projects.git_providers import (
    default_base_url_for_provider,
    get_git_provider,
)
from app.modules.projects.models import GitConnection, Project, ProjectEnvVar, ProjectMember
from app.modules.projects.schemas import (
    GitConnectionCreateRequest,
    GitConnectionPublic,
    GitProviderType,
    GitRepoSummaryPublic,
    ProjectCreateRequest,
    ProjectEnvVarPublic,
    ProjectEnvVarUpsertRequest,
    ProjectMemberAssignRequest,
    ProjectMemberPublic,
    ProjectPublic,
    ProjectRole,
    ProjectUpdateRequest,
    WorkspaceClassType,
)

projects_router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["projects"],
)


def _serialize_connection(conn: GitConnection) -> GitConnectionPublic:
    return GitConnectionPublic(
        id=conn.id,
        organization_id=conn.organization_id,
        provider=cast(GitProviderType, conn.provider),
        name=conn.name,
        base_url=conn.base_url,
        account_login=conn.account_login,
        has_token=bool(conn.encrypted_token),
        created_at=conn.created_at,
    )


def _serialize_project(project: Project) -> ProjectPublic:
    return ProjectPublic(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        git_connection_id=project.git_connection_id,
        git_provider=cast(GitProviderType, project.git_provider),
        repo_full_name=project.repo_full_name,
        repo_clone_url=project.repo_clone_url,
        default_branch=project.default_branch,
        default_workspace_class=cast(WorkspaceClassType, project.default_workspace_class),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def _get_project_or_404(
    db: AsyncSession,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project:
    project = (
        await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado.",
        )
    return project


async def _assert_project_manage_access(
    db: AsyncSession,
    user: User,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Allow org owner/admin, instance admin, or project maintainer."""
    org_member = await assert_org_access(
        db,
        user,
        organization_id,
        {"owner", "admin", "developer", "viewer"},
    )
    if user.is_instance_admin or (org_member and org_member.role in {"owner", "admin"}):
        return

    project_member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if project_member is None or project_member.role != "maintainer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol owner/admin de organización o maintainer del proyecto.",
        )


@projects_router.get("/git-connections", response_model=list[GitConnectionPublic])
async def list_git_connections(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GitConnectionPublic]:
    """List configured Git connections for an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    rows = (
        await db.execute(
            select(GitConnection)
            .where(GitConnection.organization_id == organization_id)
            .order_by(GitConnection.created_at.desc())
        )
    ).scalars().all()
    return [_serialize_connection(row) for row in rows]


@projects_router.post(
    "/git-connections",
    response_model=GitConnectionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_git_connection(
    organization_id: uuid.UUID,
    payload: GitConnectionCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GitConnectionPublic:
    """Register and optionally verify a GitHub, GitLab or OriginLabs Git connection."""
    await assert_org_access(db, user, organization_id, {"owner", "admin"})

    base_url = payload.base_url or default_base_url_for_provider(payload.provider)
    token = payload.access_token.strip() if payload.access_token else None

    if payload.provider in {"github", "gitlab"} and not token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Se requiere un token de acceso para conectar {payload.provider}.",
        )

    account_login: str | None = None
    if payload.verify:
        client = get_git_provider(provider=payload.provider, base_url=base_url, token=token)
        result = await client.verify_credentials()
        if not result.ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "No se pudieron verificar las credenciales Git.",
            )
        account_login = result.account_login

    conn = GitConnection(
        organization_id=organization_id,
        provider=payload.provider,
        name=payload.name.strip(),
        base_url=base_url,
        account_login=account_login,
        encrypted_token=encrypt_secret(token) if token else None,
        created_by_id=user.id,
    )
    db.add(conn)
    await db.flush()

    await record_audit_event(
        db,
        action="git.connection_created",
        resource_type="git_connection",
        resource_id=str(conn.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"provider": conn.provider, "account_login": conn.account_login},
    )
    await db.commit()
    await db.refresh(conn)
    return _serialize_connection(conn)


@projects_router.delete("/git-connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_git_connection(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a Git connection from an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin"})
    conn = (
        await db.execute(
            select(GitConnection).where(
                GitConnection.id == connection_id,
                GitConnection.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexión no encontrada.")

    await record_audit_event(
        db,
        action="git.connection_deleted",
        resource_type="git_connection",
        resource_id=str(conn.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"provider": conn.provider, "name": conn.name},
    )
    await db.delete(conn)
    await db.commit()


@projects_router.get(
    "/git-connections/{connection_id}/repositories",
    response_model=list[GitRepoSummaryPublic],
)
async def list_connection_repositories(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=120),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GitRepoSummaryPublic]:
    """Fetch accessible repositories using a stored encrypted Git connection."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    conn = (
        await db.execute(
            select(GitConnection).where(
                GitConnection.id == connection_id,
                GitConnection.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexión no encontrada.")

    token = decrypt_secret(conn.encrypted_token) if conn.encrypted_token else None
    client = get_git_provider(
        provider=cast(GitProviderType, conn.provider),
        base_url=conn.base_url,
        token=token,
    )
    try:
        repos = await client.list_repositories(query=q, limit=50)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudieron listar repositorios desde {conn.provider}: {exc}",
        ) from exc

    return [
        GitRepoSummaryPublic(
            full_name=repo.full_name,
            clone_url=repo.clone_url,
            default_branch=repo.default_branch,
            private=repo.private,
            provider=repo.provider,
        )
        for repo in repos
    ]


@projects_router.get("/projects", response_model=list[ProjectPublic])
async def list_projects(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectPublic]:
    """List all projects inside an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    rows = (
        await db.execute(
            select(Project)
            .where(Project.organization_id == organization_id)
            .order_by(Project.created_at.desc())
        )
    ).scalars().all()
    return [_serialize_project(row) for row in rows]


@projects_router.post(
    "/projects",
    response_model=ProjectPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    organization_id: uuid.UUID,
    payload: ProjectCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectPublic:
    """Create a project inside an organization and assign creator as maintainer."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})

    slug = payload.slug.strip().lower()
    duplicate = (
        await db.execute(
            select(Project.id).where(
                Project.organization_id == organization_id,
                Project.slug == slug,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proyecto con ese slug en la organización.",
        )

    git_provider = payload.git_provider
    if payload.git_connection_id is not None:
        conn = (
            await db.execute(
                select(GitConnection).where(
                    GitConnection.id == payload.git_connection_id,
                    GitConnection.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if conn is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La conexión Git indicada no pertenece a esta organización.",
            )
        git_provider = cast(GitProviderType, conn.provider)

    project = Project(
        organization_id=organization_id,
        name=payload.name.strip(),
        slug=slug,
        description=payload.description.strip(),
        git_connection_id=payload.git_connection_id,
        git_provider=git_provider,
        repo_full_name=payload.repo_full_name.strip() if payload.repo_full_name else None,
        repo_clone_url=payload.repo_clone_url,
        default_branch=payload.default_branch,
        default_workspace_class=payload.default_workspace_class,
        created_by_id=user.id,
    )
    db.add(project)
    await db.flush()

    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="maintainer"))
    await record_audit_event(
        db,
        action="project.created",
        resource_type="project",
        resource_id=str(project.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": project.slug, "git_provider": project.git_provider},
    )
    await db.commit()
    await db.refresh(project)
    return _serialize_project(project)


@projects_router.patch("/projects/{project_id}", response_model=ProjectPublic)
async def update_project(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectPublic:
    """Update project settings."""
    project = await _get_project_or_404(db, organization_id, project_id)
    await _assert_project_manage_access(db, user, organization_id, project.id)

    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.description is not None:
        project.description = payload.description.strip()
    if payload.git_connection_id is not None:
        conn = (
            await db.execute(
                select(GitConnection).where(
                    GitConnection.id == payload.git_connection_id,
                    GitConnection.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if conn is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conexión Git no encontrada en la organización.",
            )
        project.git_connection_id = conn.id
        project.git_provider = conn.provider
    elif payload.git_provider is not None:
        project.git_provider = payload.git_provider

    if payload.repo_full_name is not None:
        project.repo_full_name = payload.repo_full_name.strip() or None
    if payload.repo_clone_url is not None:
        project.repo_clone_url = payload.repo_clone_url
    if payload.default_branch is not None:
        project.default_branch = payload.default_branch
    if payload.default_workspace_class is not None:
        project.default_workspace_class = payload.default_workspace_class

    await record_audit_event(
        db,
        action="project.updated",
        resource_type="project",
        resource_id=str(project.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": project.slug},
    )
    await db.commit()
    await db.refresh(project)
    return _serialize_project(project)


@projects_router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project from an organization."""
    project = await _get_project_or_404(db, organization_id, project_id)
    await _assert_project_manage_access(db, user, organization_id, project.id)

    await record_audit_event(
        db,
        action="project.deleted",
        resource_type="project",
        resource_id=str(project.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": project.slug},
    )
    await db.delete(project)
    await db.commit()


@projects_router.get("/projects/{project_id}/members", response_model=list[ProjectMemberPublic])
async def list_project_members(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectMemberPublic]:
    """List team members assigned to a project."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    await _get_project_or_404(db, organization_id, project_id)

    rows = (
        await db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at.asc())
        )
    ).all()
    return [
        ProjectMemberPublic(
            id=member.id,
            project_id=member.project_id,
            user_id=member_user.id,
            email=member_user.email,
            full_name=member_user.full_name,
            role=cast(ProjectRole, member.role),
            created_at=member.created_at,
        )
        for member, member_user in rows
    ]


@projects_router.put("/projects/{project_id}/members", response_model=ProjectMemberPublic)
async def assign_project_member(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectMemberAssignRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMemberPublic:
    """Assign or update an organization member's role in a project."""
    project = await _get_project_or_404(db, organization_id, project_id)
    await _assert_project_manage_access(db, user, organization_id, project.id)

    org_member = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == payload.user_id,
            )
        )
    ).first()
    if org_member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario debe pertenecer a la organización para asignarlo al proyecto.",
        )

    _, target_user = org_member
    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == target_user.id,
            )
        )
    ).scalar_one_or_none()

    if member is None:
        member = ProjectMember(project_id=project.id, user_id=target_user.id, role=payload.role)
        db.add(member)
    else:
        member.role = payload.role

    await db.flush()
    await record_audit_event(
        db,
        action="project.member_assigned",
        resource_type="project_member",
        resource_id=str(member.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"project_slug": project.slug, "target_email": target_user.email, "role": payload.role},
    )
    await db.commit()
    await db.refresh(member)

    return ProjectMemberPublic(
        id=member.id,
        project_id=member.project_id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=cast(ProjectRole, member.role),
        created_at=member.created_at,
    )


@projects_router.delete(
    "/projects/{project_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_member(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a team member from a project."""
    project = await _get_project_or_404(db, organization_id, project_id)
    await _assert_project_manage_access(db, user, organization_id, project.id)

    member = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.id == member_id,
                ProjectMember.project_id == project.id,
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro del proyecto no encontrado.",
        )

    await record_audit_event(
        db,
        action="project.member_removed",
        resource_type="project_member",
        resource_id=str(member.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"project_slug": project.slug},
    )
    await db.delete(member)
    await db.commit()


@projects_router.get("/projects/{project_id}/env-vars", response_model=list[ProjectEnvVarPublic])
async def list_project_env_vars(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectEnvVarPublic]:
    """List encrypted project environment variables (secrets masked)."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    await _get_project_or_404(db, organization_id, project_id)

    rows = (
        await db.execute(
            select(ProjectEnvVar)
            .where(ProjectEnvVar.project_id == project_id)
            .order_by(ProjectEnvVar.key.asc())
        )
    ).scalars().all()

    results: list[ProjectEnvVarPublic] = []
    for row in rows:
        plaintext = decrypt_secret(row.encrypted_value)
        results.append(
            ProjectEnvVarPublic(
                id=row.id,
                project_id=row.project_id,
                key=row.key,
                is_secret=row.is_secret,
                value=None if row.is_secret else plaintext,
                masked_value=mask_secret(plaintext) if row.is_secret else plaintext,
                updated_at=row.updated_at,
            )
        )
    return results


@projects_router.put("/projects/{project_id}/env-vars", response_model=ProjectEnvVarPublic)
async def upsert_project_env_var(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectEnvVarUpsertRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectEnvVarPublic:
    """Create or update an encrypted environment variable for a project."""
    project = await _get_project_or_404(db, organization_id, project_id)
    await _assert_project_manage_access(db, user, organization_id, project.id)

    env_var = (
        await db.execute(
            select(ProjectEnvVar).where(
                ProjectEnvVar.project_id == project.id,
                ProjectEnvVar.key == payload.key,
            )
        )
    ).scalar_one_or_none()

    encrypted = encrypt_secret(payload.value)
    if env_var is None:
        env_var = ProjectEnvVar(
            project_id=project.id,
            key=payload.key,
            encrypted_value=encrypted,
            is_secret=payload.is_secret,
            created_by_id=user.id,
        )
        db.add(env_var)
    else:
        env_var.encrypted_value = encrypted
        env_var.is_secret = payload.is_secret

    await db.flush()
    await record_audit_event(
        db,
        action="project.env_var_saved",
        resource_type="project_env_var",
        resource_id=str(env_var.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"project_slug": project.slug, "key": env_var.key, "is_secret": env_var.is_secret},
    )
    await db.commit()
    await db.refresh(env_var)

    return ProjectEnvVarPublic(
        id=env_var.id,
        project_id=env_var.project_id,
        key=env_var.key,
        is_secret=env_var.is_secret,
        value=None if env_var.is_secret else payload.value,
        masked_value=mask_secret(payload.value) if env_var.is_secret else payload.value,
        updated_at=env_var.updated_at,
    )


@projects_router.delete(
    "/projects/{project_id}/env-vars/{env_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_env_var(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    env_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an environment variable from a project."""
    project = await _get_project_or_404(db, organization_id, project_id)
    await _assert_project_manage_access(db, user, organization_id, project.id)

    env_var = (
        await db.execute(
            select(ProjectEnvVar).where(
                ProjectEnvVar.id == env_id,
                ProjectEnvVar.project_id == project.id,
            )
        )
    ).scalar_one_or_none()
    if env_var is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variable de entorno no encontrada.",
        )

    await record_audit_event(
        db,
        action="project.env_var_deleted",
        resource_type="project_env_var",
        resource_id=str(env_var.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"project_slug": project.slug, "key": env_var.key},
    )
    await db.delete(env_var)
    await db.commit()
