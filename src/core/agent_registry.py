"""
Agent Registry & Role System — defines agent types, capabilities, and the
factory for instantiating role-specialized agents from a shared base.

This is the cornerstone of the multi-agent orchestration layer.  Each
registered role gets its own system prompt, tool allowlist, model
preferences, and handoff rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type

from .agent_core import NIMAgentCore
from .config import ConfigManager
from .providers import ProviderPool
from .signals import AgentSignals
from .tools import FileTools, TOOLS_SCHEMA
from .handoff import HANDOFF_TOOL_SCHEMA


# ════════════════════════════════════════════════════════════════════════════
# Role definitions
# ════════════════════════════════════════════════════════════════════════════

class AgentRole(str, Enum):
    """Canonical agent roles in the Emergent orchestration."""
    ORCHESTRATOR = "orchestrator"      # Plans, delegates, aggregates
    PLANNER = "planner"                # Task breakdown, dependency graph
    ARCHITECT = "architect"            # High-level design, tech decisions
    DESIGNER = "designer"              # UI/UX, component specs, design tokens
    FRONTEND = "frontend"              # React/Next.js/Vue/Svelte implementation
    BACKEND = "backend"                # API, DB, auth, business logic
    INTEGRATION = "integration"        # Third-party APIs, webhooks, SDKs
    DEVOPS = "devops"                  # CI/CD, infra, deployment, Docker
    QA = "qa"                          # Testing, linting, type-checking
    DOCS = "docs"                      # Documentation, README, API specs
    VERSION_CONTROL = "version_control"  # Git commits, PRs, branch strategy


@dataclass(frozen=True)
class AgentCapability:
    """A discrete capability an agent may possess."""
    name: str
    description: str
    required_tools: Set[str] = field(default_factory=set)
    # Optional: a callable that validates the agent can perform this capability
    validator: Optional[Callable[[NIMAgentCore], bool]] = None


@dataclass
class RoleProfile:
    """
    Complete description of an agent role — prompt, tools, model prefs,
    handoff rules, and capabilities.
    """
    role: AgentRole
    display_name: str
    description: str

    # System prompt additions (appended to base orchestrator prompt)
    system_prompt_suffix: str = ""

    # Tools this role is ALLOWED to use (subset of TOOLS_SCHEMA names)
    allowed_tools: Set[str] = field(default_factory=set)

    # Model preferences for this role (can be overridden per-instance)
    preferred_models: List[str] = field(default_factory=list)  # e.g. ["glm", "nemotron"]
    temperature: float = 0.2
    max_tokens: int = 32768

    # Handoff rules: which roles this role may delegate TO, and under what conditions
    can_delegate_to: Set[AgentRole] = field(default_factory=set)
    delegation_triggers: Dict[str, str] = field(default_factory=dict)  # keyword -> target role

    # Capabilities this role provides
    capabilities: List[AgentCapability] = field(default_factory=list)

    # Whether this role can be the "entry point" for a user request
    is_entry_role: bool = False

    # Maximum concurrent instances of this role
    max_concurrent: int = 1


# ════════════════════════════════════════════════════════════════════════════
# Built-in role profiles (can be extended via config/plugins)
# ════════════════════════════════════════════════════════════════════════════

# Tool name constants for readability
TOOL_READ = "read_file"
TOOL_WRITE = "write_file"
TOOL_SEARCH = "search_files"
TOOL_RUN = "run_command"
TOOL_HANDOFF = "handoff_task"

# Base tools every agent gets
BASE_TOOLS = {TOOL_READ, TOOL_SEARCH}

# Code-writing roles get write + run
CODE_TOOLS = BASE_TOOLS | {TOOL_WRITE, TOOL_RUN}

# Orchestrator gets everything but prefers delegation
ORCHESTRATOR_TOOLS = BASE_TOOLS | {TOOL_WRITE, TOOL_HANDOFF}  # can write plans/specs + handoff


ROLE_PROFILES: Dict[AgentRole, RoleProfile] = {
    AgentRole.ORCHESTRATOR: RoleProfile(
        role=AgentRole.ORCHESTRATOR,
        display_name="Orchestrator",
        description="Master coordinator: breaks down goals, delegates to specialists, "
                    "tracks progress, and assembles final deliverables.",
        system_prompt_suffix=(
            "\n\nYou are the ORCHESTRATOR. Your job is to:\n"
            "1. Analyze the user's goal and create a detailed execution plan.\n"
            "2. Decompose the plan into discrete tasks for specialist agents.\n"
            "3. Delegate tasks via the HANDOFF tool (see tool schema).\n"
            "4. Monitor progress, resolve blockers, and re-delegate if needed.\n"
            "5. Synthesize results into a coherent final delivery.\n\n"
            "CRITICAL: You MUST delegate implementation work to specialists. "
            "Do NOT write application code yourself. Write only plans, specs, "
            "and coordination messages.\n"
            "When delegating, provide: task_id, target_role, clear objective, "
            "context summary, and acceptance criteria."
        ),
        allowed_tools=ORCHESTRATOR_TOOLS,
        preferred_models=["glm", "nemotron"],
        temperature=0.1,
        can_delegate_to={
            AgentRole.PLANNER, AgentRole.ARCHITECT, AgentRole.DESIGNER,
            AgentRole.FRONTEND, AgentRole.BACKEND, AgentRole.INTEGRATION,
            AgentRole.DEVOPS, AgentRole.QA, AgentRole.DOCS,
            AgentRole.VERSION_CONTROL,
        },
        delegation_triggers={
            "plan": AgentRole.PLANNER,
            "architect": AgentRole.ARCHITECT,
            "design": AgentRole.DESIGNER,
            "ui": AgentRole.DESIGNER,
            "frontend": AgentRole.FRONTEND,
            "backend": AgentRole.BACKEND,
            "api": AgentRole.BACKEND,
            "database": AgentRole.BACKEND,
            "auth": AgentRole.BACKEND,
            "integration": AgentRole.INTEGRATION,
            "deploy": AgentRole.DEVOPS,
            "ci": AgentRole.DEVOPS,
            "test": AgentRole.QA,
            "lint": AgentRole.QA,
            "document": AgentRole.DOCS,
            "commit": AgentRole.VERSION_CONTROL,
            "push": AgentRole.VERSION_CONTROL,
        },
        capabilities=[
            AgentCapability("plan_creation", "Create detailed multi-agent execution plans"),
            AgentCapability("task_delegation", "Delegate tasks to specialist agents via handoff"),
            AgentCapability("progress_tracking", "Monitor and aggregate specialist progress"),
            AgentCapability("result_synthesis", "Combine specialist outputs into final delivery"),
        ],
        is_entry_role=True,
        max_concurrent=1,
    ),

    AgentRole.PLANNER: RoleProfile(
        role=AgentRole.PLANNER,
        display_name="Planner",
        description="Task decomposition, dependency analysis, and work sequencing.",
        system_prompt_suffix=(
            "\n\nYou are the PLANNER. Given a high-level goal, produce a "
            "structured task graph with:\n"
            "- Task ID, description, assigned role\n"
            "- Dependencies (task IDs that must complete first)\n"
            "- Acceptance criteria per task\n"
            "- Estimated complexity (1-5)\n"
            "Output ONLY valid JSON matching the PlanSchema. No prose."
        ),
        allowed_tools=BASE_TOOLS,
        preferred_models=["glm"],
        temperature=0.1,
        can_delegate_to=set(),  # Planner doesn't delegate further
        capabilities=[
            AgentCapability("task_decomposition", "Break goals into ordered task graphs"),
            AgentCapability("dependency_analysis", "Identify and resolve task dependencies"),
        ],
        max_concurrent=1,
    ),

    AgentRole.ARCHITECT: RoleProfile(
        role=AgentRole.ARCHITECT,
        display_name="Architect",
        description="High-level technical design: stack selection, data models, "
                    "API contracts, infrastructure topology.",
        system_prompt_suffix=(
            "\n\nYou are the ARCHITECT. Produce a Technical Design Document (TDD) "
            "covering:\n"
            "1. Technology stack decisions with rationale\n"
            "2. Data models / database schema (if applicable)\n"
            "3. API contracts (OpenAPI/GraphQL schemas)\n"
            "4. Component architecture diagram (Mermaid)\n"
            "5. Infrastructure requirements\n"
            "6. Security considerations\n"
            "7. Scalability & performance targets\n"
            "Output as structured Markdown with clear sections."
        ),
        allowed_tools=BASE_TOOLS | {TOOL_WRITE},
        preferred_models=["nemotron", "glm"],
        temperature=0.2,
        can_delegate_to=set(),
        capabilities=[
            AgentCapability("tech_stack_selection", "Choose optimal stack for requirements"),
            AgentCapability("data_modeling", "Design database schemas and relationships"),
            AgentCapability("api_design", "Define service contracts and interfaces"),
            AgentCapability("architecture_docs", "Produce comprehensive TDDs"),
        ],
    ),

    AgentRole.DESIGNER: RoleProfile(
        role=AgentRole.DESIGNER,
        display_name="Designer",
        description="UI/UX design, component specifications, design tokens, "
                    "accessibility, responsive breakpoints.",
        system_prompt_suffix=(
            "\n\nYou are the DESIGNER. Produce a Design Specification including:\n"
            "1. Design tokens (colors, spacing, typography, radii, shadows)\n"
            "2. Component inventory with variants, states, props\n"
            "3. Page/screen layouts (wireframe descriptions)\n"
            "4. User flows & interaction patterns\n"
            "5. Accessibility requirements (WCAG AA)\n"
            "6. Responsive breakpoints\n"
            "7. Animation/motion guidelines\n"
            "Output as structured Markdown + JSON token file. Reference "
            "existing design systems (Tailwind, Radix, shadcn) where applicable."
        ),
        allowed_tools=BASE_TOOLS | {TOOL_WRITE},
        preferred_models=["glm"],
        temperature=0.3,
        can_delegate_to=set(),
        capabilities=[
            AgentCapability("design_tokens", "Create consistent design token systems"),
            AgentCapability("component_specs", "Specify reusable UI components"),
            AgentCapability("user_flows", "Map user journeys and interactions"),
        ],
    ),

    AgentRole.FRONTEND: RoleProfile(
        role=AgentRole.FRONTEND,
        display_name="Frontend Engineer",
        description="Implements UI: pages, components, hooks, state, styling, "
                    "type-safety, testing. Frameworks: Next.js, React, Vue, Svelte.",
        system_prompt_suffix=(
            "\n\nYou are a SENIOR FRONTEND ENGINEER. Implement the assigned UI "
            "tasks following the Design Spec and Architect's contracts.\n"
            "Standards:\n"
            "- TypeScript strict mode, ESLint + Prettier\n"
            "- Component-driven: small, composable, typed props\n"
            "- Use design tokens, not magic values\n"
            "- Accessibility first (semantic HTML, ARIA)\n"
            "- Responsive: mobile-first, test breakpoints\n"
            "- State: React Query / Zustand / context as appropriate\n"
            "- Testing: Vitest + React Testing Library\n"
            "Write code to files via write_file. Run lint/typecheck via run_command."
        ),
        allowed_tools=CODE_TOOLS,
        preferred_models=["nemotron", "glm"],
        temperature=0.2,
        can_delegate_to={AgentRole.QA, AgentRole.DOCS},
        delegation_triggers={"test": AgentRole.QA, "document": AgentRole.DOCS},
        capabilities=[
            AgentCapability("component_implementation", "Build accessible, typed React/Vue/Svelte components"),
            AgentCapability("page_routing", "Implement pages, layouts, routing"),
            AgentCapability("state_management", "Client/server state, forms, caching"),
            AgentCapability("styling", "Tailwind/CSS Modules/Styled Components"),
        ],
    ),

    AgentRole.BACKEND: RoleProfile(
        role=AgentRole.BACKEND,
        display_name="Backend Engineer",
        description="Implements APIs, database, auth, business logic, background "
                    "jobs. Frameworks: FastAPI, Express, NestJS, Django, Go.",
        system_prompt_suffix=(
            "\n\nYou are a SENIOR BACKEND ENGINEER. Implement the assigned backend "
            "tasks per the Architect's contracts.\n"
            "Standards:\n"
            "- Type-safe: Pydantic/Zod/TypeScript, validated inputs/outputs\n"
            "- Database: migrations, indexes, RLS, connection pooling\n"
            "- Auth: JWT/OAuth, RBAC, session management\n"
            "- API: REST (OpenAPI) or GraphQL, versioned, documented\n"
            "- Observability: structured logging, metrics, tracing\n"
            "- Testing: pytest/Jest, unit + integration, contract tests\n"
            "Write code via write_file. Run migrations/tests via run_command."
        ),
        allowed_tools=CODE_TOOLS,
        preferred_models=["nemotron", "glm"],
        temperature=0.2,
        can_delegate_to={AgentRole.QA, AgentRole.DOCS, AgentRole.INTEGRATION},
        delegation_triggers={"test": AgentRole.QA, "document": AgentRole.DOCS, "integrate": AgentRole.INTEGRATION},
        capabilities=[
            AgentCapability("api_implementation", "Build type-safe REST/GraphQL APIs"),
            AgentCapability("database_design", "Migrations, models, queries, RLS"),
            AgentCapability("auth_authorization", "JWT, OAuth, RBAC, sessions"),
            AgentCapability("business_logic", "Domain services, workflows, jobs"),
        ],
    ),

    AgentRole.INTEGRATION: RoleProfile(
        role=AgentRole.INTEGRATION,
        display_name="Integration Engineer",
        description="Third-party APIs, webhooks, SDKs, payment gateways, "
                    "email/SMS, authentication providers, AI services.",
        system_prompt_suffix=(
            "\n\nYou are an INTEGRATION ENGINEER. Implement robust, observable "
            "integrations with external services.\n"
            "Standards:\n"
            "- SDK wrappers with typed interfaces\n"
            "- Retry + exponential backoff + circuit breaker\n"
            "- Webhook verification (signatures, replay protection)\n"
            "- Rate limit compliance (token bucket per provider)\n"
            "- Secrets via env vars, never hardcoded\n"
            "- Contract tests against provider sandboxes\n"
            "Write integration code via write_file. Test via run_command."
        ),
        allowed_tools=CODE_TOOLS,
        preferred_models=["glm"],
        temperature=0.2,
        can_delegate_to={AgentRole.QA, AgentRole.DOCS},
        capabilities=[
            AgentCapability("api_integration", "Wrap third-party REST/GraphQL APIs"),
            AgentCapability("webhook_handling", "Secure webhook receivers"),
            AgentCapability("sdk_wrapper", "Type-safe SDK clients"),
        ],
    ),

    AgentRole.DEVOPS: RoleProfile(
        role=AgentRole.DEVOPS,
        display_name="DevOps Engineer",
        description="CI/CD pipelines, containerization, infrastructure as code, "
                    "deployment, monitoring, secrets management.",
        system_prompt_suffix=(
            "\n\nYou are a DEVOPS ENGINEER. Build and maintain the deployment "
            "pipeline and infrastructure.\n"
            "Deliverables:\n"
            "- Dockerfile / docker-compose for local + prod\n"
            "- CI/CD: GitHub Actions / GitLab CI (lint, test, build, deploy)\n"
            "- IaC: Terraform / Pulumi for cloud resources\n"
            "- Environments: preview, staging, production\n"
            "- Secrets: vault / GitHub secrets / cloud secret manager\n"
            "- Monitoring: health checks, logging, alerting\n"
            "Write configs via write_file. Test deploy via run_command."
        ),
        allowed_tools=CODE_TOOLS,
        preferred_models=["glm"],
        temperature=0.2,
        can_delegate_to={AgentRole.QA},
        capabilities=[
            AgentCapability("ci_cd", "Design and implement pipelines"),
            AgentCapability("containerization", "Docker, multi-stage builds"),
            AgentCapability("iac", "Terraform/Pulumi for cloud resources"),
            AgentCapability("deployment", "Blue-green, canary, rollback strategies"),
        ],
    ),

    AgentRole.QA: RoleProfile(
        role=AgentRole.QA,
        display_name="QA Engineer",
        description="Testing strategy, unit/integration/e2e tests, linting, "
                    "type-checking, contract testing, performance baselines.",
        system_prompt_suffix=(
            "\n\nYou are a QA ENGINEER. Ensure code quality and correctness.\n"
            "Responsibilities:\n"
            "- Write unit tests (Vitest/Jest/pytest) for new code\n"
            "- Integration tests for API contracts\n"
            "- E2E tests (Playwright/Cypress) for critical user flows\n"
            "- Lint (ESLint/Ruff) + type-check (tsc/mypy) in CI\n"
            "- Contract tests for external integrations\n"
            "- Performance budgets (bundle size, API latency)\n"
            "Run test suites via run_command. Report failures with reproduction steps."
        ),
        allowed_tools=CODE_TOOLS,
        preferred_models=["glm"],
        temperature=0.1,
        can_delegate_to=set(),
        capabilities=[
            AgentCapability("test_authoring", "Write comprehensive test suites"),
            AgentCapability("static_analysis", "Configure and run linters/type-checkers"),
            AgentCapability("e2e_testing", "Browser automation for user flows"),
        ],
    ),

    AgentRole.DOCS: RoleProfile(
        role=AgentRole.DOCS,
        display_name="Technical Writer",
        description="Documentation: README, API docs, architecture decision "
                    "records, runbooks, onboarding guides.",
        system_prompt_suffix=(
            "\n\nYou are a TECHNICAL WRITER. Produce clear, accurate documentation.\n"
            "Deliverables:\n"
            "- README: quickstart, config, scripts, deployment\n"
            "- API docs: OpenAPI → Redoc/Swagger UI\n"
            "- ADRs: Architecture Decision Records\n"
            "- Runbooks: common operations, troubleshooting\n"
            "- Onboarding: contributor guide, code style\n"
            "Write Markdown via write_file. Keep docs in sync with code."
        ),
        allowed_tools=BASE_TOOLS | {TOOL_WRITE},
        preferred_models=["glm"],
        temperature=0.3,
        can_delegate_to=set(),
        capabilities=[
            AgentCapability("api_documentation", "Generate OpenAPI/MkDocs sites"),
            AgentCapability("adr_authoring", "Document architectural decisions"),
            AgentCapability("user_facing_docs", "Guides, tutorials, references"),
        ],
    ),

    AgentRole.VERSION_CONTROL: RoleProfile(
        role=AgentRole.VERSION_CONTROL,
        display_name="Version Control Agent",
        description="Git operations: commits, branches, PRs, merges, rebases, "
                    "changelog generation, release tagging.",
        system_prompt_suffix=(
            "\n\nYou are the VERSION CONTROL AGENT. Manage the repository.\n"
            "Operations:\n"
            "- Create feature branches per task\n"
            "- Conventional commits (feat/fix/docs/refactor/chore)\n"
            "- PR creation with description, checklist, reviewers\n"
            "- Merge strategies: squash, rebase, merge\n"
            "- Changelog generation (conventional-changelog)\n"
            "- Semantic versioning + git tags\n"
            "Execute via run_command. Never force-push shared branches."
        ),
        allowed_tools=BASE_TOOLS | {TOOL_RUN},
        preferred_models=["glm"],
        temperature=0.1,
        can_delegate_to=set(),
        capabilities=[
            AgentCapability("git_workflow", "Branching, commits, PRs, merges"),
            AgentCapability("changelog_generation", "Automated release notes"),
            AgentCapability("release_management", "Tagging, versioning, publishing"),
        ],
    ),
}


# ════════════════════════════════════════════════════════════════════════════
# Agent Factory
# ════════════════════════════════════════════════════════════════════════════

class AgentFactory:
    """
    Creates role-specialized NIMAgentCore instances from RoleProfiles.

    The factory injects role-specific configuration (prompt, tools, model)
    into a shared NIMAgentCore base, ensuring consistent behavior while
    allowing per-role customization.
    """

    def __init__(
        self,
        profile: dict,
        project_dir: str,
        signals: AgentSignals,
        provider_pool: Optional[ProviderPool] = None,
    ):
        self._base_profile = profile
        self._project_dir = project_dir
        self._signals = signals
        self._provider_pool = provider_pool

    def create_agent(
        self,
        role: AgentRole,
        *,
        model_override: Optional[str] = None,
        temperature_override: Optional[float] = None,
        max_tokens_override: Optional[int] = None,
        extra_system_prompt: str = "",
        allowed_tools_override: Optional[Set[str]] = None,
    ) -> NIMAgentCore:
        """
        Instantiate a NIMAgentCore configured for the given role.
        """
        role_profile = ROLE_PROFILES[role]

        # Determine effective configuration
        model_key = model_override or (role_profile.preferred_models[0] if role_profile.preferred_models else "glm")
        temperature = temperature_override if temperature_override is not None else role_profile.temperature
        max_tokens = max_tokens_override or role_profile.max_tokens
        allowed_tools = allowed_tools_override or role_profile.allowed_tools

        # Build a filtered TOOLS_SCHEMA for this role
        filtered_tools = [
            t for t in TOOLS_SCHEMA
            if t["function"]["name"] in allowed_tools
        ]
        # Always include handoff tool if the role can delegate
        if role_profile.can_delegate_to and HANDOFF_TOOL_SCHEMA not in filtered_tools:
            filtered_tools.append(HANDOFF_TOOL_SCHEMA)

        # Create the agent core
        agent = NIMAgentCore(
            profile=self._base_profile,
            project_dir=self._project_dir,
            signals=self._signals,
        )

        # Monkey-patch role-specific configuration
        agent._role = role
        agent._role_profile = role_profile
        agent._filtered_tools_schema = filtered_tools
        agent._role_temperature = temperature
        agent._role_max_tokens = max_tokens
        agent._role_model_key = model_key

        # Override the model selection to use role's preferred model
        original_rebuild = agent._rebuild_system

        def role_rebuild() -> None:
            original_rebuild()
            # Inject role-specific system prompt suffix
            if role_profile.system_prompt_suffix:
                sys_msg = agent.messages[0]
                sys_msg["content"] = sys_msg["content"] + role_profile.system_prompt_suffix + extra_system_prompt

        agent._rebuild_system = role_rebuild
        agent._rebuild_system()

        return agent


# ════════════════════════════════════════════════════════════════════════════
# Registry — single source of truth for roles, capabilities, and agents
# ════════════════════════════════════════════════════════════════════════════

class AgentRegistry:
    """
    Central registry for agent roles, capabilities, and running instances.

    Provides:
    - Role profile lookup
    - Capability-based agent discovery
    - Instance lifecycle tracking (for concurrency limits)
    - Dynamic role registration (for plugins/custom agents)
    """

    def __init__(self):
        self._profiles: Dict[AgentRole, RoleProfile] = dict(ROLE_PROFILES)
        self._custom_profiles: Dict[str, RoleProfile] = {}
        self._running_instances: Dict[AgentRole, int] = {r: 0 for r in AgentRole}
        self._instance_metadata: Dict[int, Dict] = {}  # agent_id -> {role, task_id, ...}

    # ----------------------------------------------------------------------
    # Role profile management
    # ----------------------------------------------------------------------
    def get_profile(self, role: AgentRole) -> RoleProfile:
        return self._profiles[role]

    def register_custom_role(self, profile: RoleProfile) -> None:
        """Register a user-defined/custom role."""
        if profile.role in self._profiles:
            raise ValueError(f"Role {profile.role} already exists")
        self._profiles[profile.role] = profile
        self._running_instances[profile.role] = 0

    def list_roles(self) -> List[AgentRole]:
        return list(self._profiles.keys())

    def list_entry_roles(self) -> List[AgentRole]:
        return [r for r, p in self._profiles.items() if p.is_entry_role]

    def find_roles_with_capability(self, capability_name: str) -> List[AgentRole]:
        return [
            r for r, p in self._profiles.items()
            if any(c.name == capability_name for c in p.capabilities)
        ]

    # ----------------------------------------------------------------------
    # Concurrency control
    # ----------------------------------------------------------------------
    def can_spawn(self, role: AgentRole) -> bool:
        profile = self._profiles[role]
        return self._running_instances.get(role, 0) < profile.max_concurrent

    def acquire_slot(self, role: AgentRole, agent_id: int, task_id: str = "") -> bool:
        if not self.can_spawn(role):
            return False
        self._running_instances[role] = self._running_instances.get(role, 0) + 1
        self._instance_metadata[agent_id] = {"role": role, "task_id": task_id}
        return True

    def release_slot(self, role: AgentRole, agent_id: int) -> None:
        self._running_instances[role] = max(0, self._running_instances.get(role, 0) - 1)
        self._instance_metadata.pop(agent_id, None)

    def get_running_count(self, role: AgentRole) -> int:
        return self._running_instances.get(role, 0)

    def get_all_running(self) -> Dict[AgentRole, int]:
        return dict(self._running_instances)

    # ----------------------------------------------------------------------
    # Delegation rules
    # ----------------------------------------------------------------------
    def can_delegate(self, from_role: AgentRole, to_role: AgentRole) -> bool:
        return to_role in self._profiles[from_role].can_delegate_to

    def resolve_delegation_target(self, from_role: AgentRole, trigger: str) -> Optional[AgentRole]:
        """Given a trigger keyword, return the target role if delegation is allowed."""
        profile = self._profiles[from_role]
        target = profile.delegation_triggers.get(trigger.lower())
        if target and self.can_delegate(from_role, target):
            return target
        return None


# Global singleton registry
_REGISTRY: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = AgentRegistry()
    return _REGISTRY


def create_factory(
    profile: dict,
    project_dir: str,
    signals: AgentSignals,
    provider_pool: Optional[ProviderPool] = None,
) -> AgentFactory:
    """Convenience function to create a factory with standard dependencies."""
    return AgentFactory(profile, project_dir, signals, provider_pool)