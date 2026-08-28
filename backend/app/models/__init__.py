from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Enum as SQLEnum, Boolean, JSON, LargeBinary
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid
import enum

Base = declarative_base()


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


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=True)
    status = Column(SQLEnum(ProjectStatus), default=ProjectStatus.PLANNING, nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    credits_used = Column(Integer, default=0)
    github_repo = Column(String(500), nullable=True)
    preview_url = Column(String(500), nullable=True)
    docker_compose = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="projects")
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="project", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="project", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    # Incremented when an account is disabled or its password changes.  Tokens
    # carry this value, allowing those operations to revoke every old session.
    auth_version = Column(Integer, default=0, nullable=False)
    credits = Column(Integer, default=1000)
    github_id = Column(String(100), nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    projects = relationship("Project", back_populates="owner")
    conversations = relationship("Conversation", back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    agent_role = Column(SQLEnum(AgentRole), nullable=True)
    meta = Column('metadata', JSON, nullable=True)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    content_type = Column(String(100), nullable=True)  # code, markdown, yaml, dockerfile, etc.
    size = Column(Integer, default=0)
    generated_by = Column(SQLEnum(AgentRole), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="artifacts")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, building, running, failed, success
    url = Column(String(500), nullable=True)
    logs = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="deployments")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    agent_role = Column(SQLEnum(AgentRole), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="agent_runs")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    amount = Column(Integer, nullable=False)  # positive for credit, negative for debit
    transaction_type = Column(String(50), nullable=False)  # purchase, usage, refund, bonus
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TokenRevocation(Base):
    __tablename__ = "token_revocations"

    token_hash = Column(String(64), primary_key=True)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PipelineJob(Base):
    """Durable pipeline state shared by every API replica."""
    __tablename__ = "pipeline_jobs"

    job_id = Column(String(32), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="queued")
    phase = Column(String(50), nullable=False, default="queued")
    artifacts = Column(JSON, nullable=False, default=list)
    preview_url = Column(String(500), nullable=True)
    errors = Column(JSON, nullable=False, default=list)
    message = Column(Text, nullable=False, default="Queued")
    prompt = Column(Text, nullable=False)
    project_dir = Column(String(1000), nullable=False)
    target = Column(String(50), nullable=False, default="web")
    use_mock = Column(Boolean, nullable=False, default=False)
    worker_id = Column(String(100), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    reserved_bytes = Column(Integer, nullable=False, default=0)
    archive_sha256 = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)


class PipelineEvent(Base):
    """Append-only event log; SSE clients consume it independently by id."""
    __tablename__ = "pipeline_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(32), ForeignKey("pipeline_jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ManagedArtifact(Base):
    """Compressed, owner-scoped delivery artifact; never publicly mounted."""
    __tablename__ = "managed_artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    pipeline_job_id = Column(String(32), ForeignKey("pipeline_jobs.job_id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False, default="application/zip")
    sha256 = Column(String(64), nullable=False, unique=True, index=True)
    byte_size = Column(Integer, nullable=False)
    object_key = Column(String(600), nullable=True, unique=True, index=True)
    payload = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
