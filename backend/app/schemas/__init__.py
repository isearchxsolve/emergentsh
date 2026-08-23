from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import enum


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    BUILDING = "building"
    TESTING = "testing"
    DEPLOYING = "deploying"
    COMPLETE = "complete"
    FAILED = "failed"


class AgentRole(str, enum.Enum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    DESIGNER = "designer"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    TESTER = "tester"
    DEPLOYER = "deployer"


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    credits: int
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# Project schemas
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    prompt: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    github_repo: Optional[str] = None
    preview_url: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: UUID
    prompt: Optional[str] = None
    status: ProjectStatus
    owner_id: UUID
    credits_used: int
    github_repo: Optional[str] = None
    preview_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectDetail(ProjectResponse):
    docker_compose: Optional[str] = None


# Conversation schemas
class ConversationBase(BaseModel):
    title: Optional[str] = None


class ConversationCreate(ConversationBase):
    pass


class ConversationResponse(ConversationBase):
    id: UUID
    project_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Message schemas
class MessageBase(BaseModel):
    role: str
    content: str
    agent_role: Optional[AgentRole] = None


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    metadata: Optional[dict] = None
    tokens_used: int
    created_at: datetime

    class Config:
        from_attributes = True


# Artifact schemas
class ArtifactBase(BaseModel):
    name: str
    path: str
    content_type: Optional[str] = None


class ArtifactCreate(ArtifactBase):
    content: Optional[str] = None
    generated_by: Optional[AgentRole] = None


class ArtifactResponse(ArtifactBase):
    id: UUID
    project_id: UUID
    content: Optional[str] = None
    size: int
    generated_by: Optional[AgentRole] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Deployment schemas
class DeploymentBase(BaseModel):
    config: Optional[dict] = None


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentResponse(DeploymentBase):
    id: UUID
    project_id: UUID
    status: str
    url: Optional[str] = None
    logs: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Agent Run schemas
class AgentRunBase(BaseModel):
    agent_role: AgentRole
    input_data: Optional[dict] = None


class AgentRunCreate(AgentRunBase):
    pass


class AgentRunResponse(AgentRunBase):
    id: UUID
    project_id: UUID
    status: str
    output_data: Optional[dict] = None
    error: Optional[str] = None
    tokens_used: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Credit schemas
class CreditTransactionResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: Optional[UUID] = None
    amount: int
    transaction_type: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# API Response schemas
class SuccessResponse(BaseModel):
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    detail: str


class PaginatedResponse(BaseModel):
    items: List[BaseModel]
    total: int
    page: int
    page_size: int
    total_pages: int