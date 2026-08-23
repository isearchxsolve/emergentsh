"""
OrchestratorWorker — QThread that drives the multi-agent orchestration loop.

This worker:
1. Owns the TaskGraph and ProjectState
2. Spawns AgentWorker instances for each task
3. Handles handoffs between agents
4. Emits orchestration-level signals to the UI
5. Manages the overall project lifecycle
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QObject, QThread, Signal

from ..core.agent_core import NIMAgentCore
from ..core.agent_registry import AgentRegistry, AgentRole, create_factory, get_registry
from ..core.config import ConfigManager
from ..core.handoff import (
    HANDOFF_TOOL_SCHEMA,
    HandoffContext,
    HandoffType,
    create_merge_handoff,
)
from ..core.providers import ProviderPool, build_provider_pool
from ..core.signals import AgentSignals
from ..core.task_graph import (
    DelegationEngine,
    ProjectState,
    Task,
    TaskGraph,
    TaskPriority,
    TaskResult,
    TaskStatus,
)
from ..workers.agent_worker import AgentWorker


class OrchestratorSignals(QObject):
    """
    Signals emitted by the OrchestratorWorker to the UI.
    These are in addition to the per-agent AgentSignals.
    """

    # Project lifecycle
    project_started = Signal(str, str)           # project_id, project_name
    project_completed = Signal(str, dict)        # project_id, summary
    project_failed = Signal(str, str)            # project_id, error

    # Task graph updates
    task_status_changed = Signal(str, str, str)  # task_id, old_status, new_status
    task_created = Signal(dict)                  # task dict
    graph_progress = Signal(int, int, int)       # completed, running, total

    # Agent management
    agent_spawned = Signal(str, str, str)        # agent_id, role, task_id
    agent_completed = Signal(str, str, dict)     # agent_id, task_id, result
    agent_failed = Signal(str, str, str)         # agent_id, task_id, error

    # Handoff events
    handoff_initiated = Signal(str, str, str)    # from_role, to_role, task_id
    handoff_completed = Signal(str, str, dict)   # from_task_id, to_task_id, payload
    escalation_received = Signal(str, str, dict) # from_role, issue, context

    # Project state
    state_updated = Signal(dict)                 # ProjectState serialized
    decision_required = Signal(str, dict)        # question, context
    agent_spawned = Signal(str, str, str)        # agent_id, role, task_id
    agent_completed = Signal(str, str, dict)     # agent_id, task_id, result
    agent_failed = Signal(str, str, str)         # agent_id, task_id, error

    # Handoff events
    handoff_initiated = Signal(str, str, str)    # from_role, to_role, task_id
    handoff_completed = Signal(str, str, dict)   # from_task_id, to_task_id, payload
    escalation_received = Signal(str, str, dict) # from_role, issue, context

    # Project state
    state_updated = Signal(dict)                 # ProjectState serialized
    decision_required = Signal(str, dict)        # question, context


class OrchestratorWorker(QThread):
    """
    Main orchestration thread. Runs the project-level event loop:
    - Initialize task graph from user goal
    - Spawn agents for READY tasks
    - Process handoffs between agents
    - Handle escalations
    - Track completion
    """

    def __init__(
        self,
        profile: dict,
        project_dir: str,
        project_name: str,
        project_goal: str,
        signals: Optional[AgentSignals] = None,
        orchestrator_signals: Optional[OrchestratorSignals] = None,
        initial_tasks: Optional[List[Task]] = None,
        project_state: Optional[ProjectState] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._profile = profile
        self._project_dir = project_dir
        self._project_name = project_name
        self._project_goal = project_goal
        self._project_id = uuid.uuid4().hex[:8]

        # Signal objects
        self._agent_signals = signals or AgentSignals()
        self._orch_signals = orchestrator_signals or OrchestratorSignals()

        # Core components
        self._registry = get_registry()
        self._factory = create_factory(profile, project_dir, self._agent_signals)
        self._provider_pool = build_provider_pool(profile)
        self._delegation_engine = DelegationEngine(self._registry)

        # State
        self._task_graph = TaskGraph()
        self._project_state = project_state or ProjectState(
            project_id=self._project_id,
            name=project_name,
        )
        self._running_agents: Dict[int, AgentWorker] = {}
        self._agent_to_task: Dict[int, str] = {}
        self._completed_task_ids: Set[str] = set()
        self._stop_requested = False
        self._max_concurrent_agents = 3

        # Initialize with provided tasks or create from goal
        if initial_tasks:
            for task in initial_tasks:
                self._task_graph.add_task(task)
        else:
            self._initialize_from_goal()

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------
    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def project_state(self) -> ProjectState:
        return self._project_state

    @property
    def task_graph(self) -> TaskGraph:
        return self._task_graph

    @property
    def agent_signals(self) -> AgentSignals:
        return self._agent_signals

    @property
    def orchestrator_signals(self) -> OrchestratorSignals:
        return self._orch_signals

    def request_stop(self) -> None:
        """Request graceful shutdown of all agents and orchestrator."""
        self._stop_requested = True
        for agent in self._running_agents.values():
            if agent.isRunning():
                agent.request_stop()

    # ----------------------------------------------------------------------
    # Main loop
    # ----------------------------------------------------------------------
    def run(self) -> None:
        """Main orchestration loop."""
        try:
            self._orch_signals.project_started.emit(self._project_id, self._project_name)
            self._orch_signals.state_updated.emit(self._project_state.to_dict())

            # Main event loop
            while not self._stop_requested:
                # 1. Check for completed agents
                self._reap_completed_agents()

                # 2. Schedule READY tasks to available agents
                self._schedule_ready_tasks()

                # 3. Check for project completion
                if self._check_project_completion():
                    break

                # 4. Brief sleep to prevent busy-wait
                time.sleep(0.5)

        except Exception as e:
            self._orch_signals.project_failed.emit(self._project_id, str(e))
            self._agent_signals.error.emit(f"Orchestrator error: {e}")
        finally:
            # Ensure all agents are stopped
            for agent in self._running_agents.values():
                if agent.isRunning():
                    agent.request_stop()
                    agent.wait(5000)

    # ----------------------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------------------
    def _initialize_from_goal(self) -> None:
        """Create initial task graph from the user's high-level goal."""
        # Create the orchestrator's planning task
        plan_task = Task(
            id=f"plan-{uuid.uuid4().hex[:6]}",
            name="Create Execution Plan",
            description=(
                f"Analyze the goal and create a detailed multi-agent execution plan. "
                f"Goal: {self._project_goal}"
            ),
            role=AgentRole.ORCHESTRATOR,
            priority=TaskPriority.CRITICAL,
            input_context={
                "goal": self._project_goal,
                "project_name": self._project_name,
                "project_dir": self._project_dir,
            },
        )
        self._task_graph.add_task(plan_task)
        self._orch_signals.task_created.emit(self._task_to_dict(plan_task))

        # The orchestrator will run this task first, which should produce
        # a plan with subsequent tasks via handoff tool calls

    # ----------------------------------------------------------------------
    # Agent lifecycle
    # ----------------------------------------------------------------------
    def _spawn_agent_for_task(self, task: Task) -> Optional[AgentWorker]:
        """Create and start an AgentWorker for the given task."""
        # Check concurrency limits
        if len(self._running_agents) >= self._max_concurrent_agents:
            return None

        role = task.role
        if not self._registry.can_spawn(role):
            return None

        # Create agent instance
        agent_core = self._factory.create_agent(role)

        # Prepare the prompt from task context
        prompt = self._build_agent_prompt(task, agent_core)

        # Create signals for this agent (they all share the same AgentSignals object
        # but we tag messages with agent_id)
        agent_signals = self._agent_signals

        # Create worker
        worker = AgentWorker(
            profile=self._profile,
            project_dir=self._project_dir,
            signals=agent_signals,
            prompt=prompt,
            resume=False,
        )

        # Store agent reference
        agent_id = id(worker)
        self._running_agents[agent_id] = worker
        self._agent_to_task[agent_id] = task.id

        # Acquire registry slot
        self._registry.acquire_slot(role, agent_id, task.id)

        # Update task
        task.status = TaskStatus.RUNNING
        task.assigned_agent_id = agent_id
        task.started_at = datetime.now()
        self._orch_signals.task_status_changed.emit(task.id, "READY", "RUNNING")
        self._orch_signals.agent_spawned.emit(str(agent_id), role.value, task.id)

        # Connect agent signals to orchestrator handlers
        worker.signals.response_finished.connect(
            lambda content, aid=agent_id, tid=task.id: self._on_agent_response(aid, tid, content)
        )
        worker.signals.tool_result.connect(
            lambda tool, result, aid=agent_id, tid=task.id: self._on_agent_tool_result(aid, tid, tool, result)
        )
        worker.signals.agent_finished.connect(
            lambda aid=agent_id: self._on_agent_finished(aid)
        )
        worker.signals.error.connect(
            lambda err, aid=agent_id, tid=task.id: self._on_agent_error(aid, tid, err)
        )

        # Add handoff tool to the agent's available tools
        # This is done by the agent_core when it sees the tool in schema

        worker.start()
        return worker

    def _reap_completed_agents(self) -> None:
        """Clean up finished agents and update task status."""
        finished_ids = []
        for agent_id, worker in list(self._running_agents.items()):
            if not worker.isRunning():
                finished_ids.append(agent_id)

        for agent_id in finished_ids:
            worker = self._running_agents.pop(agent_id, None)
            task_id = self._agent_to_task.pop(agent_id, None)

            if worker and task_id:
                task = self._task_graph.get_task(task_id)
                role = task.role if task else "unknown"

                # Release registry slot
                self._registry.release_slot(role, agent_id)

                # Update project state
                self._project_state.active_agents = len(self._running_agents)
                self._orch_signals.state_updated.emit(self._project_state.to_dict())

    def _on_agent_response(self, agent_id: int, task_id: str, content: str) -> None:
        """Handle agent's final response (after tool calls complete)."""
        task = self._task_graph.get_task(task_id)
        if not task:
            return

        # Check if the response contains a handoff
        handoff = self._parse_handoff_from_response(content, task)
        if handoff:
            self._process_handoff(agent_id, task_id, handoff)
            return

        # Otherwise, mark task as completed
        self._complete_task(task_id, content, success=True)

    def _on_agent_tool_result(self, agent_id: int, task_id: str, tool_name: str, result: str) -> None:
        """Handle tool result from agent — check for handoff tool."""
        if tool_name == "handoff_task":
            # The tool result should be the handoff payload
            try:
                handoff_data = eval(result) if isinstance(result, str) else result
                if isinstance(handoff_data, dict):
                    handoff = HandoffContext(**handoff_data)
                    self._process_handoff(agent_id, task_id, handoff)
            except Exception:
                pass  # Not a handoff, ignore

    def _on_agent_finished(self, agent_id: int) -> None:
        """Agent worker thread finished."""
        # Cleanup is handled in _reap_completed_agents
        pass

    def _on_agent_error(self, agent_id: int, task_id: str, error: str) -> None:
        """Agent reported an error."""
        task = self._task_graph.get_task(task_id)
        if task:
            task.error = error
            task.retry_count += 1
            if task.can_retry():
                task.status = TaskStatus.PENDING
                task.assigned_agent_id = None
                self._orch_signals.task_status_changed.emit(task_id, "FAILED", "PENDING")
            else:
                self._complete_task(task_id, error, success=False)

    def _complete_task(self, task_id: str, output: str, success: bool) -> None:
        """Mark a task as completed/failed and trigger dependent tasks."""
        task = self._task_graph.get_task(task_id)
        if not task:
            return

        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.output_artifacts["final_response"] = output

        old_status = "RUNNING"
        new_status = task.status.value
        self._orch_signals.task_status_changed.emit(task_id, old_status, new_status)

        self._completed_task_ids.add(task_id)
        self._orch_signals.agent_completed.emit(str(task.assigned_agent_id), task_id, {
            "success": success,
            "output": output[:500],
        })

        # Update project state
        self._project_state.completed_tasks.append(task_id)
        self._project_state.updated_at = datetime.now()
        self._orch_signals.state_updated.emit(self._project_state.to_dict())

        # If this was an orchestrator task that created a plan, parse it
        if task.role == AgentRole.ORCHESTRATOR and success:
            self._parse_orchestrator_plan(task_id, output)

    # ----------------------------------------------------------------------
    # Scheduling
    # ----------------------------------------------------------------------
    def _schedule_ready_tasks(self) -> None:
        """Find READY tasks and spawn agents for them."""
        ready_tasks = self._task_graph.get_ready_tasks(self._completed_task_ids)

        for task in ready_tasks:
            # Skip if already assigned or running
            if task.status != TaskStatus.PENDING:
                continue

            # Check if we can spawn this role
            if not self._registry.can_spawn(task.role):
                continue

            # Spawn agent
            self._spawn_agent_for_task(task)

    # ----------------------------------------------------------------------
    # Handoff processing
    # ----------------------------------------------------------------------
    def _parse_handoff_from_response(self, content: str, task: Task) -> Optional[HandoffContext]:
        """Extract handoff payload from agent's text response if present."""
        # Look for JSON handoff payload in response
        import json
        import re

        # Pattern: ```json { "to_role": ..., ... } ```
        match = re.search(r'```(?:json)?\s*(\{.*?"to_role".*?\})\s*```', content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return HandoffContext(**data)
            except Exception:
                pass

        # Pattern: direct JSON at end of response
        try:
            # Try to find last JSON object in response
            last_brace = content.rfind('}')
            if last_brace > 0:
                first_brace = content.rfind('{', 0, last_brace)
                if first_brace >= 0:
                    candidate = content[first_brace:last_brace+1]
                    data = json.loads(candidate)
                    if "to_role" in data:
                        return HandoffContext(**data)
        except Exception:
            pass

        return None

    def _process_handoff(
        self,
        from_agent_id: int,
        from_task_id: str,
        handoff: HandoffContext,
    ) -> None:
        """Process a handoff from one agent to another."""
        from_task = self._task_graph.get_task(from_task_id)
        if not from_task:
            return

        # Validate delegation is allowed
        if not self._registry.can_delegate(from_task.role, handoff.to_role):
            self._agent_signals.status_warning.emit(
                f"Delegation from {from_task.role.value} to {handoff.to_role.value} not allowed"
            )
            return

        # Emit handoff signal
        self._orch_signals.handoff_initiated.emit(
            from_task.role.value, handoff.to_role.value, from_task_id
        )

        # Create the target task
        target_task = Task(
            id=f"{handoff.to_role.value}-{uuid.uuid4().hex[:6]}",
            name=f"Delegated: {handoff.objective[:50]}",
            description=handoff.objective,
            role=handoff.to_role,
            priority=TaskPriority(handoff.priority),
            dependencies=[from_task_id],
            input_context={
                "handoff": handoff.to_dict(),
                "parent_task_id": from_task_id,
            },
        )
        self._task_graph.add_task(target_task)
        self._orch_signals.task_created.emit(self._task_to_dict(target_task))

        # Update parent task with handoff info
        from_task.output_artifacts["handoff"] = handoff.to_dict()
        from_task.output_artifacts["child_task_id"] = target_task.id

        # Emit completion
        self._orch_signals.handoff_completed.emit(from_task_id, target_task.id, handoff.to_dict())

    # ----------------------------------------------------------------------
    # Plan parsing
    # ----------------------------------------------------------------------
    def _parse_orchestrator_plan(self, task_id: str, output: str) -> None:
        """Parse the orchestrator's plan output and create tasks."""
        import json
        import re

        # Try to extract JSON plan from output
        plan_data = None
        try:
            # Look for fenced JSON
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output, re.DOTALL)
            if match:
                plan_data = json.loads(match.group(1))
            else:
                # Try to find JSON object
                last_brace = output.rfind('}')
                if last_brace > 0:
                    first_brace = output.rfind('{', 0, last_brace)
                    if first_brace >= 0:
                        plan_data = json.loads(output[first_brace:last_brace+1])
        except Exception:
            pass

        if not plan_data or "tasks" not in plan_data:
            return

        # Create tasks from plan
        for i, task_spec in enumerate(plan_data["tasks"]):
            try:
                role_str = task_spec.get("role", "frontend")
                role = AgentRole(role_str) if role_str in AgentRole._value2member_map_ else AgentRole.FRONTEND

                task = Task(
                    id=f"{role.value}-{uuid.uuid4().hex[:6]}",
                    name=task_spec.get("name", f"Task {i+1}"),
                    description=task_spec.get("description", ""),
                    role=role,
                    priority=TaskPriority(task_spec.get("priority", 50)),
                    dependencies=task_spec.get("dependencies", []),
                    input_context=task_spec.get("context", {}),
                )
                self._task_graph.add_task(task)
                self._orch_signals.task_created.emit(self._task_to_dict(task))
            except Exception as e:
                self._agent_signals.status_warning.emit(f"Failed to create task from plan: {e}")

    # ----------------------------------------------------------------------
    # Completion check
    # ----------------------------------------------------------------------
    def _check_project_completion(self) -> bool:
        """Check if all tasks are completed (success or failed)."""
        all_tasks = self._task_graph.get_all_tasks()
        if not all_tasks:
            return False

        pending_or_running = [t for t in all_tasks
                              if t.status in (TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING)]

        if not pending_or_running:
            # All tasks done
            self._orch_signals.project_completed.emit(self._project_id, {
                "total_tasks": len(all_tasks),
                "completed": len([t for t in all_tasks if t.status == TaskStatus.COMPLETED]),
                "failed": len([t for t in all_tasks if t.status == TaskStatus.FAILED]),
                "project_state": self._project_state.to_dict(),
            })
            return True

        return False

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _build_agent_prompt(self, task: Task, agent: NIMAgentCore) -> str:
        """Build the prompt for an agent starting a task."""
        context = task.input_context
        handoff = context.get("handoff")

        parts = [
            f"TASK: {task.name}",
            f"DESCRIPTION: {task.description}",
            f"ROLE: {task.role.value.upper()}",
        ]

        if handoff:
            h = handoff if isinstance(handoff, dict) else handoff.__dict__
            parts.extend([
                "",
                "HANDOFF FROM PREVIOUS AGENT:",
                f"From: {h.get('from_role', 'unknown')}",
                f"Objective: {h.get('objective', '')}",
                f"Context: {h.get('context_summary', '')}",
                f"Acceptance Criteria: {', '.join(h.get('acceptance_criteria', []))}",
            ])
            if h.get("artifacts"):
                parts.append(f"Artifacts: {h['artifacts']}")
            if h.get("files_modified"):
                parts.append(f"Files modified: {', '.join(h['files_modified'])}")
            if h.get("decisions_made"):
                parts.append(f"Decisions: {h['decisions_made']}")
            if h.get("constraints"):
                parts.append(f"Constraints: {', '.join(h['constraints'])}")
            if h.get("files_to_reference"):
                parts.append(f"Reference these files: {', '.join(h['files_to_reference'])}")
        else:
            parts.extend([
                "",
                "ORIGINAL GOAL:",
                self._project_goal,
            ])
            if task.input_context:
                parts.append(f"Additional Context: {task.input_context}")

        parts.append("")
        parts.append("Use the available tools to complete this task. When done, provide a summary of what was accomplished.")

        return "\n".join(parts)

    def _task_to_dict(self, task: Task) -> dict:
        return {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "role": task.role.value,
            "status": task.status.value,
            "priority": task.priority.value,
            "dependencies": task.dependencies,
            "dependents": task.dependents,
            "input_context": task.input_context,
            "output_artifacts": task.output_artifacts,
        }


# For backward compatibility / simple imports
__all__ = ["OrchestratorWorker", "OrchestratorSignals"]