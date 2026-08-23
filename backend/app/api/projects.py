from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import math

from backend.app.core.database import get_db
from backend.app.core.auth import get_current_active_user
from backend.app.models import Project, User, Conversation, Message, Artifact, Deployment, AgentRun
from backend.app.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetail,
    ConversationCreate, ConversationResponse,
    MessageCreate, MessageResponse,
    ArtifactCreate, ArtifactResponse,
    DeploymentCreate, DeploymentResponse,
    PaginatedResponse,
    ProjectStatus, AgentRole,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project = Project(
        name=project_data.name,
        description=project_data.description,
        prompt=project_data.prompt,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get("", response_model=PaginatedResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[ProjectStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Project).where(Project.owner_id == current_user.id)
    count_query = select(func.count(Project.id)).where(Project.owner_id == current_user.id)
    
    if status:
        query = query.where(Project.status == status)
        count_query = count_query.where(Project.status == status)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.order_by(desc(Project.updated_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    projects = result.scalars().all()
    
    return PaginatedResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
    )


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    for field, value in project_data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    
    await db.flush()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await db.delete(project)


# Conversations
@router.post("/{project_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    project_id: UUID,
    conversation_data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    conversation = Conversation(
        project_id=project_id,
        user_id=current_user.id,
        title=conversation_data.title,
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return conversation


@router.get("/{project_id}/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = await db.execute(
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .order_by(desc(Conversation.updated_at))
    )
    return result.scalars().all()


# Messages
@router.post("/{project_id}/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def create_message(
    project_id: UUID,
    conversation_id: UUID,
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.project_id == project_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    message = Message(
        conversation_id=conversation_id,
        role=message_data.role,
        content=message_data.content,
        agent_role=message_data.agent_role,
    )
    db.add(message)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(message)
    return message


@router.get("/{project_id}/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    project_id: UUID,
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.project_id == project_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


# Artifacts
@router.post("/{project_id}/artifacts", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    project_id: UUID,
    artifact_data: ArtifactCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    artifact = Artifact(
        project_id=project_id,
        name=artifact_data.name,
        path=artifact_data.path,
        content=artifact_data.content,
        content_type=artifact_data.content_type,
        size=len(artifact_data.content) if artifact_data.content else 0,
        generated_by=artifact_data.generated_by,
    )
    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)
    return artifact


@router.get("/{project_id}/artifacts", response_model=List[ArtifactResponse])
async def list_artifacts(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = await db.execute(
        select(Artifact)
        .where(Artifact.project_id == project_id)
        .order_by(Artifact.created_at)
    )
    return result.scalars().all()


# Deployments
@router.post("/{project_id}/deployments", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    project_id: UUID,
    deployment_data: DeploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    deployment = Deployment(
        project_id=project_id,
        config=deployment_data.config,
        status="pending",
    )
    db.add(deployment)
    await db.flush()
    await db.refresh(deployment)
    return deployment


@router.get("/{project_id}/deployments", response_model=List[DeploymentResponse])
async def list_deployments(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = await db.execute(
        select(Deployment)
        .where(Deployment.project_id == project_id)
        .order_by(desc(Deployment.created_at))
    )
    return result.scalars().all()


# Agent Runs
@router.get("/{project_id}/agent-runs", response_model=List[dict])
async def list_agent_runs(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.project_id == project_id)
        .order_by(desc(AgentRun.created_at))
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(run.id),
            "agent_role": run.agent_role.value,
            "status": run.status,
            "tokens_used": run.tokens_used,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "error": run.error,
        }
        for run in runs
    ]
