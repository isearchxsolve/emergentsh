"""
Emergent.sh Clone — Core Interface Stubs
========================================

This module defines the abstract interfaces (Protocol/ABC) for every major
component described in ARCHITECTURE.md §2 (Component Architecture) and §3
(Data Flow). Concrete implementations live under `src/core/` and its
sub-packages (`agents`, `orchestration`, `context`, `github`, `deployment`,
`preview`, `metering`, `auth`, `projects`, `vcs`, `telemetry`, `rag`,
`marketplace`, `mobile`, `team`, `updater`, `scaffolding`, `templates`).

These stubs are intentionally minimal — they declare the contract (method
signatures + docstrings) so that:
  1. Implementations can be written/tested against a fixed surface.
  2. Dependency injection is possible (callers depend on the Protocol, not
     the concrete class).
  3. The orchestrator can wire agents together without knowing concrete
     types.

All inference flows through the NVIDIA NIM client (OpenAI-compatible API at
`/v1/chat/completions`, `/v1/models`, `/v1/health/ready`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. NIM Inference Client (ARCHITECTURE.md §2.2 — Inference Layer)
# ─────────────────────────────────────────────────────────────────────────────

class NIMModel(str, Enum):
    """Models exposed by the NVIDIA NIM inference engine."""
    GLM_5_2 = "z-ai/glm-5.2"
    GLM_5_2_FP8 = "z-ai/glm-5.2-fp8"
    NEMOTRON_ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
    NEMOTRON_SUPER_120B = "nvidia/nemotron-3-super-120b-a12b"
    LLAMA_3_1_405B = "nvidia/llama-3.1-405b-instruct"


@dataclass
class NIMCompletionChunk:
    """One streamed chunk from `/v1/chat/completions` (stream=true)."""
    delta: str
    role: str
    finish_reason: Optional[str]
    usage_prompt: int = 0
    usage_completion: int = 0
    model: str = ""
    request_id: str = ""


@dataclass
class NIMCompletionResult:
    """Final aggregated result of a (possibly streamed) completion."""
    content: str
    role: str
    model: str
    finish_reason: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    request_id: str


class NIMClient(Protocol):
    """OpenAI-compatible client for NVIDIA NIM.

    Endpoints used:
      - POST /v1/chat/completions   (chat + streaming via SSE)
      - GET  /v1/models             (model registry discovery)
      - GET  /v1/health/ready       (health gating for the UI status bar)
    """

    base_url: str
    api_key: str
    default_model: str

    @abstractmethod
    async def health(self) -> bool:
        """Return True iff GET /v1/health/ready responds 200."""
        raise NotImplementedError

    @abstractmethod
    async def list_models(self) -> List[str]:
        """Return model ids from GET /v1/models."""
        raise NotImplementedError

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        stream: bool = False,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> NIMCompletionResult:
        """Non-streaming chat completion."""
        raise NotImplementedError

    @abstractmethod
    def stream_complete(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[NIMCompletionChunk]:
        """Streaming chat completion yielding SSE chunks until [DONE]."""
        raise NotImplementedError
        if False:  # pragma: no cover — keeps mypy happy about async-generator typing
            yield NIMCompletionChunk("", "", None)  # type: ignore[unreachable]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Agent Framework (ARCHITECTURE.md §2.3 — Agent Orchestration Engine)
# ─────────────────────────────────────────────────────────────────────────────

class AgentRole(str, Enum):
    ARCHITECT = "architect"
    DESIGNER = "designer"
    DEVELOPER = "developer"
    INTEGRATION = "integration"
    PM = "pm"


@dataclass
class AgentAction:
    """A single discrete action emitted by an agent (file write, commit, test run)."""
    agent: AgentRole
    kind: str  # "file_write" | "commit" | "test_run" | "deploy" | "message"
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: str = ""
    tokens: int = 0
    credits: float = 0.0


@dataclass
class AgentContext:
    """Shared context handed to every agent in the pipeline."""
    project_id: str
    prompt: str
    workspace_path: str
    repo_url: Optional[str] = None
    version_id: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)
    clarifications: List[str] = field(default_factory=list)
    files: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Output of a single agent's run."""
    agent: AgentRole
    success: bool
    actions: List[AgentAction] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)  # path -> content
    clarifications: List[str] = field(default_factory=list)
    error: str = ""
    next_agent: Optional[AgentRole] = None
    tokens_used: int = 0
    credits_used: float = 0.0


class BaseAgent(ABC):
    """Common interface for all 5 specialized agents.

    Each agent:
      - Receives an AgentContext + the previous AgentResult (handoff).
      - Calls the NIMClient (streaming) to produce its plan/output.
      - Emits AgentActions (file writes, commits, test runs) via the
        ActionEmitter so the WebSocket layer can stream them to the UI.
      - Returns an AgentResult consumed by the Orchestrator.
    """

    role: AgentRole
    model: str = NIMModel.GLM_5_2.value

    def __init__(self, nim: NIMClient, emitter: Optional["ActionEmitter"] = None):
        self.nim = nim
        self.emitter = emitter

    @abstractmethod
    async def run(self, ctx: AgentContext, prev: Optional[AgentResult] = None) -> AgentResult:
        raise NotImplementedError

    @abstractmethod
    def system_prompt(self, ctx: AgentContext) -> str:
        raise NotImplementedError


class ActionEmitter(Protocol):
    """Sink for streaming AgentActions to WebSocket subscribers (Redis PubSub)."""

    @abstractmethod
    async def emit(self, action: AgentAction) -> None:
        raise NotImplementedError

    @abstractmethod
    async def subscribe(self, project_id: str) -> AsyncIterator[AgentAction]:
        raise NotImplementedError
        if False:  # pragma: no cover
            yield AgentAction(AgentRole.PM, "", {})  # type: ignore[unreachable]


class Orchestrator(ABC):
    """Coordinates the 5-agent pipeline + self-debugging loop.

    Pipeline order (happy path):
      Architect → Designer → Developer → Integration → PM
    On test failure, PM triggers the self-debugging loop (max 3 iterations):
      PM → Developer → Integration → PM (re-test).
    """

    max_debug_iterations: int = 3

    @abstractmethod
    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Run the full pipeline; return the final PM AgentResult."""
        raise NotImplementedError

    @abstractmethod
    async def debug_loop(self, ctx: AgentContext, failure: AgentResult) -> AgentResult:
        """Iterate Developer→Integration→PM until tests pass or max iters hit."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 3. Task Queue & Workers (ARCHITECTURE.md §2.4 — Queue Layer)
# ─────────────────────────────────────────────────────────────────────────────

class TaskQueue(Protocol):
    """Redis-backed queue for agent build jobs (Celery/BullMQ compatible)."""

    @abstractmethod
    async def enqueue(self, project_id: str, job: Dict[str, Any]) -> str:
        """Returns job_id."""
        raise NotImplementedError

    @abstractmethod
    async def status(self, job_id: str) -> str:
        """pending | running | complete | failed."""
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, job_id: str) -> bool:
        raise NotImplementedError


class AgentWorker(ABC):
    """Consumes jobs from TaskQueue, runs the Orchestrator, streams actions."""

    @abstractmethod
    async def process(self, job: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 4. Projects, Versioning & VCS (ARCHITECTURE.md §2.5 — Data Layer)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Project:
    id: str
    owner_id: str
    name: str
    prompt: str
    repo_url: Optional[str] = None
    current_version_id: str = ""
    credits_used: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Version:
    id: str
    project_id: str
    parent_id: Optional[str]  # for forking
    agent: AgentRole
    diff_summary: str
    commit_sha: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class ProjectStore(Protocol):
    """MongoDB-backed project + version persistence."""

    @abstractmethod
    async def create_project(self, owner_id: str, prompt: str, name: str = "") -> Project:
        raise NotImplementedError

    @abstractmethod
    async def get_project(self, project_id: str) -> Optional[Project]:
        raise NotImplementedError

    @abstractmethod
    async def list_projects(self, owner_id: str) -> List[Project]:
        raise NotImplementedError

    @abstractmethod
    async def create_version(self, project_id: str, agent: AgentRole,
                              diff_summary: str, parent_id: Optional[str] = None) -> Version:
        raise NotImplementedError

    @abstractmethod
    async def list_versions(self, project_id: str) -> List[Version]:
        raise NotImplementedError

    @abstractmethod
    async def rollback(self, project_id: str, version_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def fork(self, project_id: str, version_id: Optional[str] = None) -> Project:
        """Fork to a fresh context window; preserve file tree."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 5. GitHub Integration (ARCHITECTURE.md §2.6 — GitHub Service)
# ─────────────────────────────────────────────────────────────────────────────

class GitHubClient(Protocol):
    """GitHub OAuth + repo/commit operations via Octokit/PyGithub."""

    @abstractmethod
    async def create_repo(self, owner: str, name: str, private: bool = True) -> str:
        """Returns repo_url."""
        raise NotImplementedError

    @abstractmethod
    async def commit(self, repo: str, path: str, content: str,
                      message: str, branch: str = "main") -> str:
        """Returns commit sha. Called on every agent file-write action."""
        raise NotImplementedError

    @abstractmethod
    async def push(self, repo: str, branch: str = "main") -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_oauth_url(self, state: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def exchange_code(self, code: str) -> str:
        """Returns access_token."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 6. Self-Debugging Loop (ARCHITECTURE.md §2.7 — Test Runner & Debug)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    passed: int
    failed: int
    errors: int = 0
    output: str = ""
    failing_lines: List[str] = field(default_factory=list)
    exit_code: int = 0


class TestRunner(Protocol):
    """Runs pytest/jest in the project workspace; captures structured output."""

    @abstractmethod
    async def run(self, workspace_path: str, framework: str = "pytest") -> TestResult:
        raise NotImplementedError


class DebugLoop(ABC):
    """Self-debugging loop bounded by max iterations (3 per PLAN acceptance)."""

    max_iterations: int = 3

    @abstractmethod
    async def iterate(self, ctx: AgentContext, failure: TestResult) -> AgentResult:
        """One iteration: PM diagnoses → Developer fixes → Integration re-runs."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 7. Deployment & Preview (ARCHITECTURE.md §2.8 — Deployment Service)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Deployment:
    id: str
    project_id: str
    version_id: str
    preview_url: str
    status: str  # building | ready | failed
    created_at: datetime = field(default_factory=datetime.utcnow)


class DeploymentService(Protocol):
    """One-click deploy: Docker build → push → K8s/Docker deploy → preview URL."""

    @abstractmethod
    async def deploy(self, project_id: str, version_id: str) -> Deployment:
        raise NotImplementedError

    @abstractmethod
    async def get_preview_url(self, deployment_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def status(self, deployment_id: str) -> str:
        raise NotImplementedError


class DevServerManager(Protocol):
    """Manages the live-preview dev server (Next.js dev / FastAPI uvicorn)."""

    @abstractmethod
    async def start(self, workspace_path: str) -> str:
        """Returns the preview URL (e.g. http://localhost:3000)."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def reload(self) -> None:
        """Debounced reload after Developer agent emits a file write."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 8. Auth, Metering & Rate Limiting (ARCHITECTURE.md §2.9 — Cross-Cutting)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class User:
    id: str
    email: str
    github_login: Optional[str] = None
    credits: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


class AuthService(Protocol):
    """NextAuth.js (frontend) + JWT (backend) + GitHub OAuth."""

    @abstractmethod
    async def sign_in_with_github(self, code: str) -> User:
        raise NotImplementedError

    @abstractmethod
    async def sign_in_with_email(self, email: str) -> str:
        """Returns magic-link token."""
        raise NotImplementedError

    @abstractmethod
    async def verify_jwt(self, token: str) -> Optional[User]:
        raise NotImplementedError


class CreditLedger(Protocol):
    """Per-user credit accounting; debited on every NIM completion."""

    @abstractmethod
    async def balance(self, user_id: str) -> float:
        raise NotImplementedError

    @abstractmethod
    async def debit(self, user_id: str, amount: float, reason: str = "") -> bool:
        raise NotImplementedError

    @abstractmethod
    async def credit(self, user_id: str, amount: float, reason: str = "") -> bool:
        raise NotImplementedError


class RateLimiter(Protocol):
    """Token-bucket per user/project keyed on NIM RPM (shared bucket model)."""

    @abstractmethod
    async def acquire(self, key: str, tokens: int = 1) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def wait_time(self, key: str) -> float:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 9. Telemetry & Monitoring (ARCHITECTURE.md §2.10 — Observability)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MetricPoint:
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TelemetrySink(Protocol):
    """Prometheus-compatible metrics + Grafana dashboards."""

    @abstractmethod
    async def record(self, point: MetricPoint) -> None:
        raise NotImplementedError

    @abstractmethod
    async def counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 10. WebSocket / Real-time (ARCHITECTURE.md §2.11 — Real-time Layer)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WSMessage:
    """Envelope for all WebSocket messages (agent actions, build state, health)."""
    type: str  # "agent_action" | "build_state" | "nim_health" | "credits" | "error"
    project_id: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class WebSocketHub(Protocol):
    """FastAPI WebSocket + Redis PubSub fan-out to connected UI clients."""

    @abstractmethod
    async def publish(self, project_id: str, msg: WSMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    async def subscribe(self, project_id: str) -> AsyncIterator[WSMessage]:
        raise NotImplementedError
        if False:  # pragma: no cover
            yield WSMessage("", "", {})  # type: ignore[unreachable]


# ─────────────────────────────────────────────────────────────────────────────
# 11. RAG / Context Window Management (ARCHITECTURE.md §2.12 — Context Layer)
# ─────────────────────────────────────────────────────────────────────────────

class ContextStore(Protocol):
    """Vector + KV store for context-window management & forking.

    Backs the Fork action (reset chat, keep file tree) and the version
    timeline so long builds don't blow the NIM context window.
    """

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError

    @abstractmethod
    async def query(self, embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def compact(self, project_id: str) -> int:
        """Returns tokens saved by compaction."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 12. Scaffolding & Templates (ARCHITECTURE.md §2.13 — Generation Layer)
# ─────────────────────────────────────────────────────────────────────────────

class ScaffoldGenerator(Protocol):
    """Generates the Next.js + FastAPI + MongoDB project skeleton."""

    @abstractmethod
    async def generate(self, spec: Dict[str, Any], workspace_path: str) -> List[str]:
        """Returns list of created file paths."""
        raise NotImplementedError


class TemplateLibrary(Protocol):
    """Reusable code templates emitted by the Developer agent."""

    @abstractmethod
    async def get(self, name: str, **vars: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    async def list_templates(self) -> List[str]:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 13. Marketplace, Team, Mobile, Updater (ARCHITECTURE.md §2.14 — Extensions)
# ─────────────────────────────────────────────────────────────────────────────

class MarketplaceClient(Protocol):
    """Agent/template marketplace (mirrors Emergent.sh marketplace)."""

    @abstractmethod
    async def list_agents(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def install_agent(self, agent_id: str) -> bool:
        raise NotImplementedError


class TeamManager(Protocol):
    """Multi-user team collaboration on a project."""

    @abstractmethod
    async def add_member(self, project_id: str, user_id: str, role: str = "member") -> bool:
        raise NotImplementedError

    @abstractmethod
    async def list_members(self, project_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class MobileBridge(Protocol):
    """Mobile companion app bridge (push build state, receive prompts)."""

    @abstractmethod
    async def notify(self, user_id: str, title: str, body: str) -> bool:
        raise NotImplementedError


class Updater(Protocol):
    """Self-update mechanism for the desktop shell."""

    @abstractmethod
    async def check_for_update(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def apply_update(self, version_id: str) -> bool:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# 14. Dependency Injection Container (ARCHITECTURE.md §3 — Data Flow wiring)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ServiceContainer:
    """Composition root — wires concrete implementations behind the Protocols.

    The FastAPI app builds one of these at startup and injects it into routers
    via Depends(). Tests substitute fakes here.
    """
    nim: NIMClient
    orchestrator: Orchestrator
    queue: TaskQueue
    projects: ProjectStore
    github: GitHubClient
    test_runner: TestRunner
    debug_loop: DebugLoop
    deployment: DeploymentService
    dev_server: DevServerManager
    auth: AuthService
    credits: CreditLedger
    rate_limiter: RateLimiter
    telemetry: TelemetrySink
    websocket: WebSocketHub
    context: ContextStore
    scaffold: ScaffoldGenerator
    templates: TemplateLibrary
    marketplace: MarketplaceClient
    team: TeamManager
    mobile: MobileBridge
    updater: Updater


__all__ = [
    # NIM
    "NIMModel", "NIMCompletionChunk", "NIMCompletionResult", "NIMClient",
    # Agents
    "AgentRole", "AgentAction", "AgentContext", "AgentResult", "BaseAgent",
    "ActionEmitter", "Orchestrator",
    # Queue
    "TaskQueue", "AgentWorker",
    # Projects / VCS
    "Project", "Version", "ProjectStore",
    # GitHub
    "GitHubClient",
    # Debug
    "TestResult", "TestRunner", "DebugLoop",
    # Deploy / Preview
    "Deployment", "DeploymentService", "DevServerManager",
    # Auth / Metering
    "User", "AuthService", "CreditLedger", "RateLimiter",
    # Telemetry
    "MetricPoint", "TelemetrySink",
    # WebSocket
    "WSMessage", "WebSocketHub",
    # Context
    "ContextStore",
    # Scaffolding
    "ScaffoldGenerator", "TemplateLibrary",
    # Extensions
    "MarketplaceClient", "TeamManager", "MobileBridge", "Updater",
    # DI
    "ServiceContainer",
]
