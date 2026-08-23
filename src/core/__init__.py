"""
Core package — headless agentic engine (no UI dependencies).
"""

from .agent_core import NIMAgentCore
from .agent_registry import (
    AgentRole,
    AgentCapability,
    RoleProfile,
    AgentFactory,
    AgentRegistry,
    get_registry,
    create_factory,
    ROLE_PROFILES,
)
from .auth import (
    AuthManager,
    Credential,
    UserSession,
    WindowsCredentialManager,
    CredentialEncryption,
    CreditManager,
    TokenUsage,
    Budget,
    UsageSummary,
    create_auth_manager,
    get_auth_manager,
    create_credit_manager,
    get_credit_manager,
)
from .config import ConfigManager
from .context import (
    ContextManager,
    ContextWindow,
    ContextUpdate,
    ContextManager,
    ContextSelector,
    StreamingContextManager,
)
from .deployment import (
    DeploymentConfig,
    DeploymentResult,
    GitHubRepo,
    DeploymentProvider,
    VercelProvider,
    NetlifyProvider,
    FlyProvider,
    RailwayProvider,
    RenderProvider,
    CustomProvider,
    DeploymentManager,
    create_deployment_manager,
    get_provider,
    list_providers,
    PROVIDERS,
)
from .github import (
    GitHubClient,
    GitHubManager,
    GitHubUser,
    GitHubRepo,
    GitHubBranch,
    GitHubCommit,
    GitHubPR,
    GitHubIssue,
    GitHubWorkflowRun,
    create_github_client,
    create_github_manager,
)
from .handoff import (
    HandoffContext,
    HandoffType,
    HANDOFF_TOOL_SCHEMA,
    create_delegation_handoff,
    create_escalation_handoff,
    create_consultation_handoff,
    create_merge_handoff,
)
from .mobile import (
    MobileTemplate,
    MobileTemplateEngine,
    ExpoDevClientManager,
    MobilePreviewWidget,
    MOBILE_TEMPLATES,
)
from .rag import (
    DocumentChunk,
    SearchResult,
    IndexStats,
    EmbeddingProvider,
    SentenceTransformerEmbedding,
    OpenAIEmbedding,
    VectorIndex,
    CodeChunker,
    RAGManager,
)
from .telemetry import (
    TelemetryManager,
    TelemetryEvent,
    CrashReport,
    create_telemetry_manager,
    get_telemetry_manager,
)
from .updater import (
    UpdateManager,
    UpdateInfo,
    UpdateProgress,
    UpdateChannel,
    BackgroundUpdateChecker,
    create_update_manager,
    MSIBuilder,
)
from .context import (
    ContextManager,
    ContextWindow,
    ContextUpdate,
    ContextManager,
    ContextSelector,
    StreamingContextManager,
)
from .rag import (
    DocumentChunk,
    SearchResult,
    IndexStats,
    EmbeddingProvider,
    SentenceTransformerEmbedding,
    OpenAIEmbedding,
    VectorIndex,
    CodeChunker,
    RAGManager,
)
from .mobile import (
    MobileTemplate,
    MobileTemplateEngine,
    ExpoDevClientManager,
    MobilePreviewWidget,
    MOBILE_TEMPLATES,
)
from .updater import (
    UpdateManager,
    UpdateInfo,
    UpdateProgress,
    UpdateChannel,
    BackgroundUpdateChecker,
    create_update_manager,
    MSIBuilder,
)
from .telemetry import (
    TelemetryManager,
    TelemetryEvent,
    CrashReport,
    create_telemetry_manager,
    get_telemetry_manager,
)
from .config import ConfigManager
from .deployment import (
    DeploymentConfig,
    DeploymentResult,
    GitHubRepo,
    DeploymentProvider,
    VercelProvider,
    NetlifyProvider,
    FlyProvider,
    RailwayProvider,
    RenderProvider,
    CustomProvider,
    DeploymentManager,
    create_deployment_manager,
    get_provider,
    list_providers,
    PROVIDERS,
)
from .github import (
    GitHubClient,
    GitHubManager,
    GitHubUser,
    GitHubRepo,
    GitHubBranch,
    GitHubCommit,
    GitHubPR,
    GitHubIssue,
    GitHubWorkflowRun,
    create_github_client,
    create_github_manager,
)
from .handoff import (
    HandoffContext,
    HandoffType,
    HANDOFF_TOOL_SCHEMA,
    create_delegation_handoff,
    create_escalation_handoff,
    create_consultation_handoff,
    create_merge_handoff,
)
from .mobile import (
    MobileTemplate,
    MobileTemplateEngine,
    ExpoDevClientManager,
    MobilePreviewWidget,
    MOBILE_TEMPLATES,
)
from .rag import (
    DocumentChunk,
    SearchResult,
    IndexStats,
    EmbeddingProvider,
    SentenceTransformerEmbedding,
    OpenAIEmbedding,
    VectorIndex,
    CodeChunker,
    RAGManager,
)
from .telemetry import (
    TelemetryManager,
    TelemetryEvent,
    CrashReport,
    create_telemetry_manager,
    get_telemetry_manager,
)
from .updater import (
    UpdateManager,
    UpdateInfo,
    UpdateProgress,
    UpdateChannel,
    BackgroundUpdateChecker,
    create_update_manager,
    MSIBuilder,
)
from .context import (
    ContextManager,
    ContextWindow,
    ContextUpdate,
    ContextManager,
    ContextSelector,
    StreamingContextManager,
)
from .rag import (
    DocumentChunk,
    SearchResult,
    IndexStats,
    EmbeddingProvider,
    SentenceTransformerEmbedding,
    OpenAIEmbedding,
    VectorIndex,
    CodeChunker,
    RAGManager,
)
from .mobile import (
    MobileTemplate,
    MobileTemplateEngine,
    ExpoDevClientManager,
    MobilePreviewWidget,
    MOBILE_TEMPLATES,
)
from .updater import (
    UpdateManager,
    UpdateInfo,
    UpdateProgress,
    UpdateChannel,
    BackgroundUpdateChecker,
    create_update_manager,
    MSIBuilder,
)
from .telemetry import (
    TelemetryManager,
    TelemetryEvent,
    CrashReport,
    create_telemetry_manager,
    get_telemetry_manager,
)
from .config import ConfigManager
from .deployment import (
    DeploymentConfig,
    DeploymentResult,
    GitHubRepo,
    DeploymentProvider,
    VercelProvider,
    NetlifyProvider,
    FlyProvider,
    RailwayProvider,
    RenderProvider,
    CustomProvider,
    DeploymentManager,
    create_deployment_manager,
    get_provider,
    list_providers,
    PROVIDERS,
)
from .github import (
    GitHubClient,
    GitHubManager,
    GitHubUser,
    GitHubRepo,
    GitHubBranch,
    GitHubCommit,
    GitHubPR,
    GitHubIssue,
    GitHubWorkflowRun,
    create_github_client,
    create_github_manager,
)
from .handoff import (
    HandoffContext,
    HandoffType,
    HANDOFF_TOOL_SCHEMA,
    create_delegation_handoff,
    create_escalation_handoff,
    create_consultation_handoff,
    create_merge_handoff,
)
from .models import (
    ModelProvider,
    ModelCapability,
    ModelInfo,
    ModelRegistry,
    ModelClientFactory,
    get_model_registry,
    get_model_factory,
    create_model_client,
    get_model_selector_options,
)
from .workspace import (
    WorkspaceManager,
    get_workspace,
    Profile,
    Project,
    TaskRecord,
    Artifact,
    Session,
    Deployment,
    SCHEMA_VERSION,
)
from .team import (
    TeamWorkspaceManager,
    Team,
    TeamRole,
    TeamMember,
    TeamInvitation,
    InvitationStatus,
    ActivityEvent,
    SharedSession,
    create_team_workspace,
    get_team_workspace,
)
from .providers import ProviderPool, build_provider_pool
from .rate_limiter import TokenBucket, TokenMeter
from .signals import AgentSignals
from .task_graph import (
    Task,
    TaskStatus,
    TaskPriority,
    TaskResult,
    TaskGraph,
    DelegationEngine,
    ProjectState,
)
from .tools import FileTools, TOOLS_SCHEMA, execute_tool
from .handoff import (
    HandoffContext,
    HandoffType,
    HANDOFF_TOOL_SCHEMA,
    create_delegation_handoff,
    create_escalation_handoff,
    create_consultation_handoff,
    create_merge_handoff,
)
from .workspace import (
    WorkspaceManager,
    get_workspace,
    Profile,
    Project,
    TaskRecord,
    Artifact,
    Session,
    Deployment,
    SCHEMA_VERSION,
)
from .team import (
    TeamWorkspaceManager,
    Team,
    TeamRole,
    TeamMember,
    TeamInvitation,
    InvitationStatus,
    ActivityEvent,
    SharedSession,
    create_team_workspace,
    get_team_workspace,
)
from .providers import ProviderPool, build_provider_pool
from .rate_limiter import TokenBucket, TokenMeter
from .signals import AgentSignals
from .task_graph import (
    Task,
    TaskStatus,
    TaskPriority,
    TaskResult,
    TaskGraph,
    DelegationEngine,
    ProjectState,
)
from .tools import FileTools, TOOLS_SCHEMA, execute_tool
from .handoff import (
    HandoffContext,
    HandoffType,
    HANDOFF_TOOL_SCHEMA,
    create_delegation_handoff,
    create_escalation_handoff,
    create_consultation_handoff,
    create_merge_handoff,
)
from .workspace import (
    WorkspaceManager,
    get_workspace,
    Profile,
    Project,
    TaskRecord,
    Artifact,
    Session,
    Deployment,
    SCHEMA_VERSION,
)
from .team import (
    TeamWorkspaceManager,
    Team,
    TeamRole,
    TeamMember,
    TeamInvitation,
    InvitationStatus,
    ActivityEvent,
    SharedSession,
    create_team_workspace,
    get_team_workspace,
)
from .providers import ProviderPool, build_provider_pool
from .rate_limiter import TokenBucket, TokenMeter
from .signals import AgentSignals
from .task_graph import (
    Task,
    TaskStatus,
    TaskPriority,
    TaskResult,
    TaskGraph,
    DelegationEngine,
    ProjectState,
)
from .tools import FileTools, TOOLS_SCHEMA, execute_tool
from .handoff import (
    HandoffContext,
    HandoffType,
    HANDOFF_TOOL_SCHEMA,
    create_delegation_handoff,
    create_escalation_handoff,
    create_consultation_handoff,
    create_merge_handoff,
)
from .workspace import (
    WorkspaceManager,
    get_workspace,
    Profile,
    Project,
    TaskRecord,
    Artifact,
    Session,
    Deployment,
    SCHEMA_VERSION,
)
from .team import (
    TeamWorkspaceManager,
    Team,
    TeamRole,
    TeamMember,
    TeamInvitation,
    InvitationStatus,
    ActivityEvent,
    SharedSession,
    create_team_workspace,
    get_team_workspace,
)
from .providers import ProviderPool, build_provider_pool
from .rate_limiter import TokenBucket, TokenMeter
from .signals import AgentSignals
from .task_graph import (
    Task,
    TaskStatus,
    TaskPriority,
    TaskResult,
    TaskGraph,
    DelegationEngine,
    ProjectState,
)
from .tools import FileTools, TOOLS_SCHEMA, execute_tool

__all__ = [
    # Agent core
    "NIMAgentCore",
    # Agent registry & roles
    "AgentRole",
    "AgentCapability",
    "RoleProfile",
    "AgentFactory",
    "AgentRegistry",
    "get_registry",
    "create_factory",
    "ROLE_PROFILES",
    # Auth & Credits
    "AuthManager",
    "Credential",
    "UserSession",
    "WindowsCredentialManager",
    "CredentialEncryption",
    "CreditManager",
    "TokenUsage",
    "Budget",
    "UsageSummary",
    "create_auth_manager",
    "get_auth_manager",
    "create_credit_manager",
    "get_credit_manager",
    # Config
    "ConfigManager",
    # Handoff
    "HandoffContext",
    "HandoffType",
    "HANDOFF_TOOL_SCHEMA",
    "create_delegation_handoff",
    "create_escalation_handoff",
    "create_consultation_handoff",
    "create_merge_handoff",
    # Workspace
    "WorkspaceManager",
    "get_workspace",
    "Profile",
    "Project",
    "TaskRecord",
    "Artifact",
    "Session",
    "Deployment",
    "SCHEMA_VERSION",
    # Deployment
    "DeploymentConfig",
    "DeploymentResult",
    "GitHubRepo",
    "DeploymentProvider",
    "VercelProvider",
    "NetlifyProvider",
    "FlyProvider",
    "RailwayProvider",
    "RenderProvider",
    "CustomProvider",
    "DeploymentManager",
    "create_deployment_manager",
    "get_provider",
    "list_providers",
    "PROVIDERS",
    # GitHub
    "GitHubClient",
    "GitHubManager",
    "GitHubUser",
    "GitHubRepo",
    "GitHubBranch",
    "GitHubCommit",
    "GitHubPR",
    "GitHubIssue",
    "GitHubWorkflowRun",
    "create_github_client",
    "create_github_manager",
    # Models
    "ModelProvider",
    "ModelCapability",
    "ModelInfo",
    "ModelRegistry",
    "ModelClientFactory",
    "get_model_registry",
    "get_model_factory",
    "create_model_client",
    "get_model_selector_options",
    # Handoff
    "HandoffContext",
    "HandoffType",
    "HANDOFF_TOOL_SCHEMA",
    "create_delegation_handoff",
    "create_escalation_handoff",
    "create_consultation_handoff",
    "create_merge_handoff",
    # Workspace
    "WorkspaceManager",
    "get_workspace",
    "Profile",
    "Project",
    "TaskRecord",
    "Artifact",
    "Session",
    "Deployment",
    "SCHEMA_VERSION",
    # Providers
    "ProviderPool",
    "build_provider_pool",
    # Rate limiting
    "TokenBucket",
    "TokenMeter",
    # Signals
    "AgentSignals",
    # Task graph
    "Task",
    "TaskStatus",
    "TaskPriority",
    "TaskResult",
    "TaskGraph",
    "DelegationEngine",
    "ProjectState",
    # Tools
    "FileTools",
    "TOOLS_SCHEMA",
    "execute_tool",
]