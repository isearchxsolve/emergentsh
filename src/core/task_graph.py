"""
Task Graph & Delegation Engine — models the work as a directed acyclic graph
of tasks with dependencies, handles scheduling, and manages agent delegation.

This is the orchestration brain: it decides what runs when, which agent
gets which task, and how results flow between tasks.
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .agent_registry import AgentRegistry, AgentRole, get_registry


# ════════════════════════════════════════════════════════════════════════════
# Task definitions
# ════════════════════════════════════════════════════════════════════════════

class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"          # All dependencies satisfied, waiting for agent
    RUNNING = "running"      # Agent actively working
    COMPLETED = "completed"  # Finished successfully
    FAILED = "failed"        # Error or timeout
    BLOCKED = "blocked"      # Waiting on external factor
    CANCELLED = "cancelled"  # Explicitly cancelled


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


@dataclass
class Task:
    """
    A single unit of work in the orchestration graph.

    Tasks form a DAG: edges = dependencies (task B depends on task A).
    When all dependencies are COMPLETED, the task becomes READY.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    role: AgentRole = AgentRole.ORCHESTRATOR
    priority: TaskPriority = TaskPriority.NORMAL

    # Dependency graph
    dependencies: List[str] = field(default_factory=list)  # task IDs that must complete first
    dependents: List[str] = field(default_factory=list)    # task IDs that depend on this

    # Context passed from parent/delegator
    input_context: Dict[str, Any] = field(default_factory=dict)

    # Outputs produced by the agent
    output_artifacts: Dict[str, Any] = field(default_factory=dict)

    # Execution tracking
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2

    # Metadata
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_ready(self, completed_task_ids: Set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep_id in completed_task_ids for dep_id in self.dependencies)

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    success: bool
    artifacts: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    handoff_payload: Optional[Dict[str, Any]] = None  # For delegation
    agent_reasoning: str = ""
    tokens_used: int = 0


# ════════════════════════════════════════════════════════════════════════════
# Task Graph
# ════════════════════════════════════════════════════════════════════════════

class TaskGraph:
    """
    Directed acyclic graph of tasks with dependency resolution and scheduling.

    Provides:
    - Topological ordering for execution
    - Ready-task queue management
    - Cycle detection
    - Progress tracking
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)    # task_id -> dependent_ids
        self._reverse_adj: Dict[str, Set[str]] = defaultdict(set)  # task_id -> dependency_ids

    def add_task(self, task: Task) -> None:
        """Add a task to the graph."""
        if task.id in self._tasks:
            raise ValueError(f"Task {task.id} already exists")
        self._tasks[task.id] = task
        # Build adjacency
        for dep_id in task.dependencies:
            self._adjacency[dep_id].add(task.id)
            self._reverse_adj[task.id].add(dep_id)
            # Update dependent's dependents list
            if dep_id in self._tasks:
                self._tasks[dep_id].dependents.append(task.id)

    def remove_task(self, task_id: str) -> None:
        """Remove a task and its edges."""
        if task_id not in self._tasks:
            return
        # Remove from dependents' dependency lists
        for dep_id in self._reverse_adj[task_id]:
            if dep_id in self._tasks:
                self._tasks[dep_id].dependents = [
                    d for d in self._tasks[dep_id].dependents if d != task_id
                ]
        # Remove from dependencies' dependent lists
        for dep_id in self._adjacency[task_id]:
            if dep_id in self._tasks:
                self._tasks[dep_id].dependencies = [
                    d for d in self._tasks[dep_id].dependencies if d != task_id
                ]
        del self._tasks[task_id]
        self._adjacency.pop(task_id, None)
        self._reverse_adj.pop(task_id, None)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return list(self._tasks.values())

    def get_ready_tasks(self, completed_ids: Set[str]) -> List[Task]:
        """Get all tasks whose dependencies are satisfied and are PENDING."""
        ready = []
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING and task.is_ready(completed_ids):
                ready.append(task)
        # Sort by priority (highest first), then by creation order
        ready.sort(key=lambda t: (-t.priority.value, t.id))
        return ready

    def get_running_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def get_completed_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.FAILED]

    def topological_order(self) -> List[str]:
        """Return a valid topological ordering of all task IDs."""
        in_degree = {tid: len(self._reverse_adj[tid]) for tid in self._tasks}
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            tid = queue.popleft()
            order.append(tid)
            for succ in self._adjacency[tid]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(order) != len(self._tasks):
            raise ValueError("Graph has cycles!")
        return order

    def has_cycles(self) -> bool:
        try:
            self.topological_order()
            return False
        except ValueError:
            return True

    def get_dependents(self, task_id: str) -> List[Task]:
        return [self._tasks[d] for d in self._adjacency.get(task_id, set()) if d in self._tasks]

    def get_dependencies(self, task_id: str) -> List[Task]:
        return [self._tasks[d] for d in self._reverse_adj.get(task_id, set()) if d in self._tasks]

    def progress_stats(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for t in self._tasks.values():
            counts[t.status.value] += 1
        return dict(counts)


# ════════════════════════════════════════════════════════════════════════════
# Delegation Engine
# ════════════════════════════════════════════════════════════════════════════

class DelegationEngine:
    """
    Handles task delegation between agents based on role capabilities
    and registry rules.
    """

    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or get_registry()

    def find_best_role_for_task(self, task: Task) -> AgentRole:
        """
        Determine the best agent role for a task based on its description,
        tags, and required capabilities.
        """
        # If role is explicitly set and valid, use it
        if task.role in self.registry.list_roles():
            return task.role

        # Infer from tags/keywords
        tag_role_map = {
            "plan": AgentRole.PLANNER,
            "architect": AgentRole.ARCHITECT,
            "design": AgentRole.DESIGNER,
            "ui": AgentRole.DESIGNER,
            "frontend": AgentRole.FRONTEND,
            "react": AgentRole.FRONTEND,
            "backend": AgentRole.BACKEND,
            "api": AgentRole.BACKEND,
            "database": AgentRole.BACKEND,
            "auth": AgentRole.BACKEND,
            "integration": AgentRole.INTEGRATION,
            "webhook": AgentRole.INTEGRATION,
            "deploy": AgentRole.DEVOPS,
            "ci": AgentRole.DEVOPS,
            "docker": AgentRole.DEVOPS,
            "test": AgentRole.QA,
            "lint": AgentRole.QA,
            "docs": AgentRole.DOCS,
            "git": AgentRole.VERSION_CONTROL,
        }

        # Check tags first
        for tag in task.tags:
            if tag.lower() in tag_role_map:
                return tag_role_map[tag.lower()]

        # Check description/name for keywords
        text = f"{task.name} {task.description}".lower()
        for keyword, role in tag_role_map.items():
            if keyword in text:
                return role

        # Default to orchestrator for unclassified tasks
        return AgentRole.ORCHESTRATOR

    def validate_delegation(self, from_role: AgentRole, to_role: AgentRole) -> bool:
        """Check if delegation is allowed per registry rules."""
        return self.registry.can_delegate(from_role, to_role)

    def create_delegated_task(
        self,
        parent_task: Task,
        to_role: AgentRole,
        name: str,
        description: str,
        input_context: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """Create a new task delegated to another role."""
        return Task(
            name=name,
            description=description,
            role=to_role,
            dependencies=[parent_task.id],
            input_context=input_context or {},
            priority=parent_task.priority,
            tags={"delegated", f"from-{parent_task.role.value}"},
            metadata={"parent_task_id": parent_task.id},
        )

    def create_handoff_task(
        self,
        from_task: Task,
        to_role: AgentRole,
        handoff_payload: Dict[str, Any],
    ) -> Task:
        """Create a handoff task with structured context transfer."""
        return self.create_delegated_task(
            parent_task=from_task,
            to_role=to_role,
            name=f"Handoff: {from_task.name} → {to_role.value}",
            description=f"Receive handoff from {from_task.role.value} and continue work",
            input_context={
                "handoff_from": from_task.role.value,
                "handoff_payload": handoff_payload,
                "parent_artifacts": from_task.output_artifacts,
            },
            priority=TaskPriority.HIGH,
        )


# ════════════════════════════════════════════════════════════════════════════
# Project State (shared context across all agents)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ProjectState:
    """
    Shared mutable state accessible to all agents in a project.

    This is the "source of truth" for the project — file tree, decisions,
    specifications, and generated artifacts. Agents read/write to coordinate.
    """
    project_id: str
    name: str
    description: str = ""

    # Technical decisions made during planning/architect
    tech_stack: Dict[str, str] = field(default_factory=dict)  # e.g. {"frontend": "nextjs", "backend": "fastapi"}
    architecture_decisions: List[Dict[str, Any]] = field(default_factory=list)

    # Specifications
    requirements: List[str] = field(default_factory=list)
    design_spec: Dict[str, Any] = field(default_factory=dict)  # UI/UX spec from designer
    api_spec: Dict[str, Any] = field(default_factory=dict)     # OpenAPI spec from backend

    # File system state
    file_tree: Dict[str, Any] = field(default_factory=dict)   # Virtual FS for generated files
    generated_files: Dict[str, str] = field(default_factory=dict)  # path -> content

    # Artifacts produced by agents
    artifacts: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # task_id -> artifacts

    # Git state
    git_branch: str = "main"
    git_commits: List[Dict[str, Any]] = field(default_factory=list)
    pending_changes: Dict[str, str] = field(default_factory=dict)  # path -> status

    # Deployment
    deployment_target: Optional[str] = None
    deployment_url: Optional[str] = None
    environment_variables: Dict[str, str] = field(default_factory=dict)

    # Progress tracking
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    current_phase: str = "init"

    def update_timestamp(self) -> None:
        self.updated_at = datetime.now()

    def add_artifact(self, task_id: str, artifacts: Dict[str, Any]) -> None:
        self.artifacts[task_id] = artifacts
        self.update_timestamp()

    def add_generated_file(self, path: str, content: str) -> None:
        self.generated_files[path] = content
        self.update_timestamp()

    def get_context_for_role(self, role: AgentRole) -> Dict[str, Any]:
        """Extract relevant context subset for a specific agent role."""
        base = {
            "project_id": self.project_id,
            "project_name": self.name,
            "tech_stack": self.tech_stack,
            "current_phase": self.current_phase,
        }

        if role in (AgentRole.PLANNER, AgentRole.ARCHITECT, AgentRole.ORCHESTRATOR):
            return {**base, "requirements": self.requirements, "decisions": self.architecture_decisions}

        if role == AgentRole.DESIGNER:
            return {**base, "requirements": self.requirements, "design_spec": self.design_spec}

        if role == AgentRole.FRONTEND:
            return {
                **base,
                "design_spec": self.design_spec,
                "api_spec": self.api_spec,
                "generated_files": {k: v for k, v in self.generated_files.items() if k.startswith("frontend/")},
            }

        if role == AgentRole.BACKEND:
            return {
                **base,
                "api_spec": self.api_spec,
                "requirements": self.requirements,
                "generated_files": {k: v for k, v in self.generated_files.items() if k.startswith("backend/")},
            }

        if role == AgentRole.INTEGRATION:
            return {**base, "api_spec": self.api_spec, "environment_variables": self.environment_variables}

        if role == AgentRole.DEVOPS:
            return {**base, "tech_stack": self.tech_stack, "deployment_target": self.deployment_target}

        if role == AgentRole.VERSION_CONTROL:
            return {**base, "pending_changes": self.pending_changes, "git_branch": self.git_branch}

        return base