"""API endpoints for Knowledge Base, Team Chat and Tasks."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.audit.service import record_audit_event
from app.modules.collab.models import (
    KnowledgeDoc,
    KnowledgeFolder,
    TeamChannel,
    TeamMessage,
    TeamTask,
)
from app.modules.collab.schemas import (
    KnowledgeDocCreateRequest,
    KnowledgeDocPublic,
    KnowledgeDocUpdateRequest,
    KnowledgeFolderCreateRequest,
    KnowledgeFolderPublic,
    TaskStatus,
    TeamChannelCreateRequest,
    TeamChannelPublic,
    TeamMessageCreateRequest,
    TeamMessagePublic,
    TeamTaskCreateRequest,
    TeamTaskPublic,
    TeamTaskUpdateRequest,
)
from app.modules.identity.dependencies import assert_org_access, get_client_ip, get_current_user
from app.modules.identity.models import User

collab_router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["collaboration"],
)


@collab_router.get("/knowledge/folders", response_model=list[KnowledgeFolderPublic])
async def list_knowledge_folders(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeFolder]:
    """List knowledge folders in an organization."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    rows = (
        await db.execute(
            select(KnowledgeFolder)
            .where(KnowledgeFolder.organization_id == organization_id)
            .order_by(KnowledgeFolder.name.asc())
        )
    ).scalars().all()
    return list(rows)


@collab_router.post(
    "/knowledge/folders",
    response_model=KnowledgeFolderPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_folder(
    organization_id: uuid.UUID,
    payload: KnowledgeFolderCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeFolder:
    """Create a folder inside the organization knowledge base."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    folder = KnowledgeFolder(
        organization_id=organization_id,
        parent_id=payload.parent_id,
        project_id=payload.project_id,
        name=payload.name.strip(),
        slug=payload.slug.strip().lower(),
        created_by_id=user.id,
    )
    db.add(folder)
    await db.flush()
    await record_audit_event(
        db,
        action="knowledge.folder_created",
        resource_type="knowledge_folder",
        resource_id=str(folder.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": folder.slug},
    )
    await db.commit()
    await db.refresh(folder)
    return folder


@collab_router.delete(
    "/knowledge/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_folder(
    organization_id: uuid.UUID,
    folder_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a knowledge folder (documents remain unassigned)."""
    await assert_org_access(db, user, organization_id, {"owner", "admin"})
    folder = (
        await db.execute(
            select(KnowledgeFolder).where(
                KnowledgeFolder.id == folder_id,
                KnowledgeFolder.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carpeta no encontrada.")
    await db.delete(folder)
    await db.commit()


@collab_router.get("/knowledge/docs", response_model=list[KnowledgeDocPublic])
async def list_knowledge_docs(
    organization_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    tag: str | None = Query(default=None, max_length=32),
    q: str | None = Query(default=None, max_length=120),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeDoc]:
    """List knowledge documents with optional folder, tag and text filters."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    stmt = select(KnowledgeDoc).where(KnowledgeDoc.organization_id == organization_id)
    if folder_id is not None:
        stmt = stmt.where(KnowledgeDoc.folder_id == folder_id)
    if q and q.strip():
        stmt = stmt.where(KnowledgeDoc.title.ilike(f"%{q.strip()}%"))

    docs = list((await db.execute(stmt.order_by(desc(KnowledgeDoc.updated_at)))).scalars().all())
    if tag and tag.strip():
        needle = tag.strip().lower()
        docs = [doc for doc in docs if needle in (doc.tags or [])]
    return docs


@collab_router.post(
    "/knowledge/docs",
    response_model=KnowledgeDocPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_doc(
    organization_id: uuid.UUID,
    payload: KnowledgeDocCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDoc:
    """Create a Markdown knowledge document."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    doc = KnowledgeDoc(
        organization_id=organization_id,
        folder_id=payload.folder_id,
        title=payload.title.strip(),
        content=payload.content,
        tags=payload.tags,
        is_favorite=payload.is_favorite,
        created_by_id=user.id,
        author_email=user.email,
    )
    db.add(doc)
    await db.flush()
    await record_audit_event(
        db,
        action="knowledge.doc_created",
        resource_type="knowledge_doc",
        resource_id=str(doc.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"title": doc.title},
    )
    await db.commit()
    await db.refresh(doc)
    return doc


@collab_router.patch("/knowledge/docs/{doc_id}", response_model=KnowledgeDocPublic)
async def update_knowledge_doc(
    organization_id: uuid.UUID,
    doc_id: uuid.UUID,
    payload: KnowledgeDocUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDoc:
    """Update a knowledge document."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    doc = (
        await db.execute(
            select(KnowledgeDoc).where(
                KnowledgeDoc.id == doc_id,
                KnowledgeDoc.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado.",
        )

    if payload.title is not None:
        doc.title = payload.title.strip()
    if payload.content is not None:
        doc.content = payload.content
    if payload.folder_id is not None:
        doc.folder_id = payload.folder_id
    if payload.tags is not None:
        doc.tags = payload.tags
    if payload.is_favorite is not None:
        doc.is_favorite = payload.is_favorite

    await db.commit()
    await db.refresh(doc)
    return doc


@collab_router.delete("/knowledge/docs/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_doc(
    organization_id: uuid.UUID,
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a knowledge document."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    doc = (
        await db.execute(
            select(KnowledgeDoc).where(
                KnowledgeDoc.id == doc_id,
                KnowledgeDoc.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado.",
        )
    await db.delete(doc)
    await db.commit()


@collab_router.get("/chat/channels", response_model=list[TeamChannelPublic])
async def list_chat_channels(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeamChannel]:
    """List team chat channels, auto-seeding #general if none exist yet."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    rows = list(
        (
            await db.execute(
                select(TeamChannel)
                .where(TeamChannel.organization_id == organization_id)
                .order_by(TeamChannel.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        general = TeamChannel(
            organization_id=organization_id,
            name="general",
            slug="general",
            description="Canal principal del equipo.",
            created_by_id=user.id,
        )
        db.add(general)
        await db.commit()
        await db.refresh(general)
        rows = [general]
    return rows


@collab_router.post(
    "/chat/channels",
    response_model=TeamChannelPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_channel(
    organization_id: uuid.UUID,
    payload: TeamChannelCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamChannel:
    """Create a new team chat channel."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    slug = payload.slug.strip().lower()
    exists = (
        await db.execute(
            select(TeamChannel.id).where(
                TeamChannel.organization_id == organization_id,
                TeamChannel.slug == slug,
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un canal con ese slug.",
        )

    channel = TeamChannel(
        organization_id=organization_id,
        project_id=payload.project_id,
        name=payload.name.strip(),
        slug=slug,
        description=payload.description.strip(),
        created_by_id=user.id,
    )
    db.add(channel)
    await db.flush()
    await record_audit_event(
        db,
        action="chat.channel_created",
        resource_type="team_channel",
        resource_id=str(channel.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"slug": channel.slug},
    )
    await db.commit()
    await db.refresh(channel)
    return channel


@collab_router.get(
    "/chat/channels/{channel_id}/messages",
    response_model=list[TeamMessagePublic],
)
async def list_channel_messages(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeamMessage]:
    """List recent messages inside a team channel."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    channel = (
        await db.execute(
            select(TeamChannel.id).where(
                TeamChannel.id == channel_id,
                TeamChannel.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal no encontrado.")

    rows = (
        await db.execute(
            select(TeamMessage)
            .where(TeamMessage.channel_id == channel_id)
            .order_by(TeamMessage.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


@collab_router.post(
    "/chat/channels/{channel_id}/messages",
    response_model=TeamMessagePublic,
    status_code=status.HTTP_201_CREATED,
)
async def post_channel_message(
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload: TeamMessageCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamMessage:
    """Post a message or private note to a team channel."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    channel = (
        await db.execute(
            select(TeamChannel.id).where(
                TeamChannel.id == channel_id,
                TeamChannel.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canal no encontrado.")

    msg = TeamMessage(
        channel_id=channel_id,
        sender_user_id=user.id,
        sender_name=user.full_name,
        sender_email=user.email,
        body=payload.body.strip(),
        is_private_note=payload.is_private_note,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@collab_router.get("/tasks", response_model=list[TeamTaskPublic])
async def list_tasks(
    organization_id: uuid.UUID,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeamTask]:
    """List tasks for an organization with optional status filter."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer", "viewer"})
    stmt = select(TeamTask).where(TeamTask.organization_id == organization_id)
    if status_filter is not None:
        stmt = stmt.where(TeamTask.status == status_filter)
    rows = (await db.execute(stmt.order_by(desc(TeamTask.updated_at)))).scalars().all()
    return list(rows)


@collab_router.post(
    "/tasks",
    response_model=TeamTaskPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    organization_id: uuid.UUID,
    payload: TeamTaskCreateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamTask:
    """Create a task standalone or linked from a chat message."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    task = TeamTask(
        organization_id=organization_id,
        project_id=payload.project_id,
        source_message_id=payload.source_message_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        status="pending",
        priority=payload.priority,
        assignee_user_id=payload.assignee_user_id,
        created_by_id=user.id,
    )
    db.add(task)
    await db.flush()
    await record_audit_event(
        db,
        action="task.created",
        resource_type="team_task",
        resource_id=str(task.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"title": task.title, "priority": task.priority},
    )
    await db.commit()
    await db.refresh(task)
    return task


@collab_router.patch("/tasks/{task_id}", response_model=TeamTaskPublic)
async def update_task(
    organization_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TeamTaskUpdateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamTask:
    """Update a task status, priority, title or assignee."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    task = (
        await db.execute(
            select(TeamTask).where(
                TeamTask.id == task_id,
                TeamTask.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada.")

    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.description is not None:
        task.description = payload.description.strip()
    if payload.status is not None:
        task.status = payload.status
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.assignee_user_id is not None:
        task.assignee_user_id = payload.assignee_user_id

    await record_audit_event(
        db,
        action="task.updated",
        resource_type="team_task",
        resource_id=str(task.id),
        actor=user,
        organization_id=organization_id,
        ip_address=get_client_ip(request),
        details={"status": task.status, "priority": task.priority},
    )
    await db.commit()
    await db.refresh(task)
    return task


@collab_router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    organization_id: uuid.UUID,
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a team task."""
    await assert_org_access(db, user, organization_id, {"owner", "admin", "developer"})
    task = (
        await db.execute(
            select(TeamTask).where(
                TeamTask.id == task_id,
                TeamTask.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada.")
    await db.delete(task)
    await db.commit()
