"""Workspaces API endpoints: lifecycle, Caddy forward_auth routing and PTY WebSocket."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.core.database import async_session_factory, get_db
from app.modules.audit.service import record_audit_event
from app.modules.identity.dependencies import assert_org_access, get_client_ip, get_current_user
from app.modules.identity.models import User
from app.modules.identity.sessions import resolve_session_user_id
from app.modules.projects.git_providers import GitProviderType, build_ephemeral_git_env
from app.modules.projects.models import GitConnection, Project, ProjectEnvVar
from app.modules.system.monitoring import HostMetrics, collect_host_metrics, evaluate_admission
from app.modules.workspaces.models import Workspace
from app.modules.workspaces.orchestrator import (
    DEFAULT_WORKSPACE_IMAGE,
    WORKSPACE_CLASS_SPECS,
    WorkspaceOrchestrator,
    build_workspace_url,
)
from app.modules.workspaces.schemas import (
    WorkspaceClass,
    WorkspaceCreateRequest,
    WorkspacePublic,
    WorkspaceStatus,
)

workspaces_router = APIRouter(
    prefix="/organizations/{organization_id}/workspaces",
    tags=["workspaces"],
)


def _serialize_workspace(ws: Workspace) -> WorkspacePublic:
    settings = get_settings()
    return WorkspacePublic(
        id=ws.id,
        organization_id=ws.organization_id,
        project_id=ws.project_id,
        owner_user_id=ws.owner_user_id,
        name=ws.name,
        slug=ws.slug,
        workspace_class=cast(WorkspaceClass, ws.workspace_class),
        image=ws.image,
        status=cast(WorkspaceStatus, ws.status),
        container_id=ws.container_id,
        container_name=ws.container_name,
        volume_name=ws.volume_name,
        subdomain=ws.subdomain,
        ide_url=build_workspace_url(
            ws.subdomain,
            settings.originlabs_domain,
            secure=settings.cookie_secure,
        ),
        idle_timeout_minutes=ws.idle_timeout_minutes,
        last_activity_at=ws.last_activity_at,
        started_at=ws.started_at,
        stopped_at=ws.stopped_at,
        last_error=ws.last_error,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


async def _get_workspace_or_404(
    db: AsyncSession,
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Workspace:
    ws = (
        await db.execute(
            select(Workspace).where(
                Workspace.id == workspace_id,
                Workspace.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if ws is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace no encontrado.",
        )
    return ws


async def _collect_running_metrics(db: AsyncSession) -> HostMetrics:
    running = (
        await db.execute(select(Workspace).where(Workspace.status == "running"))
    ).scalars().all()
    alloc_cpu = sum(
        WORKSPACE_CLASS_SPECS[cast(WorkspaceClass, item.workspace_class)].cpu_cores
        for item in running
    )
    alloc_ram = sum(
        WORKSPACE_CLASS_SPECS[cast(WorkspaceClass, item.workspace_class)].ram_mb
        for item in running
    )
    return await asyncio.to_thread(
        collect_host_metrics,
        running_workspaces=len(running),
        allocated_cpu_cores=alloc_cpu,
        allocated_ram_mb=alloc_ram,
    )


async def _build_workspace_env(db: AsyncSession, project: Project) -> dict[str, str]:
    env_rows = (
        await db.execute(select(ProjectEnvVar).where(ProjectEnvVar.project_id == project.id))
    ).scalars().all()
    env_vars = {row.key: decrypt_secret(row.encrypted_value) for row in env_rows}

    if project.repo_clone_url:
        env_vars["ORIGINLABS_REPO_URL"] = project.repo_clone_url
        env_vars["ORIGINLABS_REPO_BRANCH"] = project.default_branch

    if project.git_connection_id is not None:
        conn = (
            await db.execute(
                select(GitConnection).where(GitConnection.id == project.git_connection_id)
            )
        ).scalar_one_or_none()
        if conn is not None:
            token = decrypt_secret(conn.encrypted_token) if conn.encrypted_token else None
            env_vars.update(
                build_ephemeral_git_env(
                    provider=cast(GitProviderType, conn.provider),
                    token=token,
                )
            )
    return env_vars


async def _start_workspace_runtime(
    db: AsyncSession,
    ws: Workspace,
    project: Project,
    actor: User,
    request: Request,
) -> None:
    metrics = await _collect_running_metrics(db)
    decision = evaluate_admission(metrics, cast(WorkspaceClass, ws.workspace_class))
    if not decision.allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=decision.reason)

    settings = get_settings()
    orchestrator = WorkspaceOrchestrator(caddy_admin_url=settings.caddy_admin_url)
    env_vars = await _build_workspace_env(db, project)

    try:
        container_id = await asyncio.to_thread(
            orchestrator.start_container,
            workspace_id=str(ws.id),
            organization_id=str(ws.organization_id),
            project_id=str(ws.project_id),
            container_name=ws.container_name,
            volume_name=ws.volume_name,
            workspace_class=cast(WorkspaceClass, ws.workspace_class),
            image=ws.image,
            env_vars=env_vars,
        )
    except RuntimeError as exc:
        ws.status = "error"
        ws.last_error = str(exc)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    base_host = settings.originlabs_domain.split(":")[0].strip().lower() or "localhost"
    await orchestrator.register_caddy_route(
        workspace_id=str(ws.id),
        host=f"{ws.subdomain}.{base_host}",
        container_name=ws.container_name,
    )

    now = datetime.now(UTC)
    ws.status = "running"
    ws.container_id = container_id
    ws.started_at = now
    ws.last_activity_at = now
    ws.last_error = None
    await record_audit_event(
        db,
        action="workspace.started",
        resource_type="workspace",
        resource_id=str(ws.id),
        actor=actor,
        organization_id=ws.organization_id,
        ip_address=get_client_ip(request),
        details={"slug": ws.slug, "class": ws.workspace_class},
    )
    await db.commit()
    await db.refresh(ws)


@workspaces_router.get("", response_model=list[WorkspacePublic])
async def list_workspaces(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspacePublic]:
    """List all workspaces belonging to an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    rows = (
        await db.execute(
            select(Workspace)
            .where(Workspace.organization_id == organization_id)
            .order_by(Workspace.created_at.desc())
        )
    ).scalars().all()
    return [_serialize_workspace(row) for row in rows]


@workspaces_router.post("", response_model=WorkspacePublic, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    organization_id: uuid.UUID,
    payload: WorkspaceCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspacePublic:
    """Create a workspace linked to a project and optionally start it."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})

    project = (
        await db.execute(
            select(Project).where(
                Project.id == payload.project_id,
                Project.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proyecto seleccionado no pertenece a esta organización.",
        )

    slug = payload.slug.strip().lower()
    dup = (
        await db.execute(
            select(Workspace.id).where(
                Workspace.organization_id == organization_id,
                Workspace.slug == slug,
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un workspace con ese slug en la organización.",
        )

    ws_id = uuid.uuid4()
    short_id = str(ws_id).split("-")[0]
    ws = Workspace(
        id=ws_id,
        organization_id=organization_id,
        project_id=project.id,
        owner_user_id=user.id,
        name=payload.name.strip(),
        slug=slug,
        workspace_class=payload.workspace_class,
        image=DEFAULT_WORKSPACE_IMAGE,
        status="stopped",
        container_name=f"ol-ws-{short_id}",
        volume_name=f"ol_ws_{short_id}_data",
        subdomain=f"ws-{short_id}",
        idle_timeout_minutes=payload.idle_timeout_minutes,
    )
    db.add(ws)
    await db.flush()

    await record_audit_event(
        db,
        action="workspace.created",
        resource_type="workspace",
        resource_id=str(ws.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": ws.slug, "project_id": str(project.id), "class": ws.workspace_class},
    )
    await db.commit()
    await db.refresh(ws)

    if payload.auto_start:
        await _start_workspace_runtime(db, ws, project, user, request)

    return _serialize_workspace(ws)


@workspaces_router.post("/{workspace_id}/start", response_model=WorkspacePublic)
async def start_workspace(
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspacePublic:
    """Start an isolated workspace container after admission control checks."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    ws = await _get_workspace_or_404(db, organization_id, workspace_id)
    project = (
        await db.execute(select(Project).where(Project.id == ws.project_id))
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto asociado no encontrado.",
        )
    await _start_workspace_runtime(db, ws, project, user, request)
    return _serialize_workspace(ws)


@workspaces_router.post("/{workspace_id}/stop", response_model=WorkspacePublic)
async def stop_workspace(
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspacePublic:
    """Stop a running workspace container while keeping its persistent volume."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    ws = await _get_workspace_or_404(db, organization_id, workspace_id)
    settings = get_settings()
    orchestrator = WorkspaceOrchestrator(caddy_admin_url=settings.caddy_admin_url)

    try:
        await asyncio.to_thread(orchestrator.stop_container, ws.container_name)
    except RuntimeError as exc:
        ws.last_error = str(exc)

    await orchestrator.remove_caddy_route(workspace_id=str(ws.id))
    ws.status = "stopped"
    ws.stopped_at = datetime.now(UTC)

    await record_audit_event(
        db,
        action="workspace.stopped",
        resource_type="workspace",
        resource_id=str(ws.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": ws.slug},
    )
    await db.commit()
    await db.refresh(ws)
    return _serialize_workspace(ws)


@workspaces_router.post("/{workspace_id}/heartbeat", response_model=WorkspacePublic)
async def workspace_heartbeat(
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspacePublic:
    """Record active IDE/terminal usage to defer idle auto-stop."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    ws = await _get_workspace_or_404(db, organization_id, workspace_id)
    ws.last_activity_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(ws)
    return _serialize_workspace(ws)


@workspaces_router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    request: Request,
    purge_volume: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a workspace container, Caddy route and optionally its persistent volume."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    ws = await _get_workspace_or_404(db, organization_id, workspace_id)
    settings = get_settings()
    orchestrator = WorkspaceOrchestrator(caddy_admin_url=settings.caddy_admin_url)

    try:
        await asyncio.to_thread(
            orchestrator.remove_container,
            container_name=ws.container_name,
            volume_name=ws.volume_name,
            purge_volume=purge_volume,
        )
    except RuntimeError:
        pass

    await orchestrator.remove_caddy_route(workspace_id=str(ws.id))
    await record_audit_event(
        db,
        action="workspace.deleted",
        resource_type="workspace",
        resource_id=str(ws.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": ws.slug, "purge_volume": purge_volume},
    )
    await db.delete(ws)
    await db.commit()


@workspaces_router.websocket("/{workspace_id}/terminal")
async def workspace_terminal_ws(
    websocket: WebSocket,
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> None:
    """Authenticated WebSocket bridge for executing commands inside a workspace."""
    settings = get_settings()
    raw_token = websocket.cookies.get(settings.session_cookie_name)
    if not raw_token:
        await websocket.close(code=4401)
        return

    user_id = await resolve_session_user_id(raw_token)
    if user_id is None:
        await websocket.close(code=4401)
        return

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=4401)
            return

        try:
            await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
            ws = await _get_workspace_or_404(db, organization_id, workspace_id)
        except HTTPException:
            await websocket.close(code=4403)
            return

        await websocket.accept()
        ws.last_activity_at = datetime.now(UTC)
        await db.commit()

        await websocket.send_text(
            f"[originlabs] Conectado a terminal de '{ws.name}' (estado: {ws.status})."
        )
        orchestrator = WorkspaceOrchestrator(caddy_admin_url=settings.caddy_admin_url)

        try:
            while True:
                command = (await websocket.receive_text()).strip()
                if not command:
                    continue
                ws.last_activity_at = datetime.now(UTC)
                await db.commit()

                if ws.status != "running":
                    await websocket.send_text(
                        "[originlabs] El workspace está detenido. Inícialo primero."
                    )
                    continue

                try:
                    code, output = await asyncio.to_thread(
                        orchestrator.exec_command,
                        ws.container_name,
                        command,
                    )
                    rendered = output.rstrip() or f"(exit {code})"
                    await websocket.send_text(rendered)
                except RuntimeError as exc:
                    await websocket.send_text(f"[originlabs][error] {exc}")
        except WebSocketDisconnect:
            return
