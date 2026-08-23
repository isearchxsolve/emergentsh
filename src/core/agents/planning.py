"""
PlanningAgent — responsible for project planning, task decomposition, and roadmap creation.

The PlanningAgent analyzes requirements, breaks them into actionable tasks,
creates dependency graphs, and produces project plans with milestones.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


@dataclass
class ProjectPlan:
    """A complete project plan with tasks, milestones, and dependencies."""
    project_id: str
    name: str
    description: str
    tasks: List[AgentTask] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    estimated_duration_days: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TaskBreakdown:
    """Result of breaking down a high-level requirement into tasks."""
    parent_task_id: str
    subtasks: List[AgentTask]
    dependencies: Dict[str, List[str]]  # task_id -> list of dependency task_ids
    critical_path: List[str]


class PlanningAgent(BaseAgent):
    """
    Agent specialized in project planning and task decomposition.
    
    Capabilities:
    - Requirements analysis and clarification
    - Task decomposition and dependency mapping
    - Milestone planning and timeline estimation
    - Resource allocation planning
    - Risk assessment and mitigation planning
    - Sprint/iteration planning
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.ANALYTICAL,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        capabilities = [
            AgentCapability(
                name="requirements_analysis",
                description="Analyze and clarify project requirements",
                tool_names=["analyze_requirements", "ask_clarifying_questions"],
                produces_artifacts=["requirements_doc", "clarification_questions"],
            ),
            AgentCapability(
                name="task_decomposition",
                description="Break down high-level goals into executable tasks",
                tool_names=["decompose_task", "create_task_graph"],
                produces_artifacts=["task_list", "dependency_graph"],
            ),
            AgentCapability(
                name="milestone_planning",
                description="Create project milestones and timelines",
                tool_names=["create_milestones", "estimate_timeline"],
                produces_artifacts=["milestone_plan", "timeline"],
            ),
            AgentCapability(
                name="risk_assessment",
                description="Identify project risks and mitigation strategies",
                tool_names=["assess_risks", "create_mitigation_plan"],
                produces_artifacts=["risk_register", "mitigation_plan"],
            ),
            AgentCapability(
                name="sprint_planning",
                description="Plan sprints and iterations",
                tool_names=["plan_sprint", "allocate_capacity"],
                produces_artifacts=["sprint_plan", "capacity_plan"],
            ),
        ]

        system_prompt = """You are a Planning Agent in the emergent.sh multi-agent system.
Your role is to analyze requirements, decompose work into actionable tasks,
create project plans with milestones, and identify risks.

You operate with an ANALYTICAL personality: methodical, data-driven, and thorough.
You produce structured plans that other agents can execute.

Key responsibilities:
1. Analyze incoming requirements for completeness and clarity
2. Break down complex features into atomic, executable tasks
3. Map dependencies between tasks to create execution order
4. Estimate effort and create realistic timelines
5. Identify risks and propose mitigation strategies
6. Create sprint plans for iterative delivery

Output format: Always produce structured JSON artifacts that can be consumed by other agents.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.PLANNING,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute planning task based on task type."""
        self.set_task(task)
        self.set_context(context)

        task_type = task.input_data.get("type", "plan_project")

        if task_type == "analyze_requirements":
            return self._analyze_requirements(task.input_data)
        elif task_type == "decompose_task":
            return self._decompose_task(task.input_data)
        elif task_type == "create_project_plan":
            return self._create_project_plan(task.input_data)
        elif task_type == "plan_sprint":
            return self._plan_sprint(task.input_data)
        elif task_type == "assess_risks":
            return self._assess_risks(task.input_data)
        else:
            return self._create_project_plan(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base

    def _analyze_requirements(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze and clarify requirements."""
        requirements = input_data.get("requirements", "")
        self.emit_status("Analyzing requirements...", "info")

        # TODO: Implement actual LLM-based analysis
        # For now, return structured analysis
        return {
            "requirements_doc": {
                "functional_requirements": [],
                "non_functional_requirements": [],
                "constraints": [],
                "assumptions": [],
            },
            "clarification_questions": [],
            "completeness_score": 0.8,
        }

    def _decompose_task(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decompose a high-level task into subtasks."""
        parent_task = input_data.get("parent_task", {})
        self.emit_status("Decomposing task...", "info")

        # TODO: Implement actual LLM-based decomposition
        return {
            "subtasks": [],
            "dependencies": {},
            "critical_path": [],
        }

    def _create_project_plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a complete project plan."""
        project_name = input_data.get("project_name", "Unnamed Project")
        requirements = input_data.get("requirements", "")
        self.emit_status(f"Creating project plan for {project_name}...", "info")

        # TODO: Implement actual LLM-based planning
        plan = ProjectPlan(
            project_id=input_data.get("project_id", "proj-001"),
            name=project_name,
            description=requirements,
        )

        return {
            "project_plan": {
                "project_id": plan.project_id,
                "name": plan.name,
                "description": plan.description,
                "tasks": [t.__dict__ for t in plan.tasks],
                "milestones": plan.milestones,
                "estimated_duration_days": plan.estimated_duration_days,
            },
            "task_graph": {},
            "resource_plan": {},
        }

    def _plan_sprint(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan a sprint with capacity allocation."""
        sprint_number = input_data.get("sprint_number", 1)
        available_capacity = input_data.get("capacity_hours", 40)
        self.emit_status(f"Planning sprint {sprint_number}...", "info")

        return {
            "sprint_plan": {
                "sprint_number": sprint_number,
                "tasks": [],
                "capacity_allocated": 0,
                "capacity_remaining": available_capacity,
            },
            "capacity_plan": {},
        }

    def _assess_risks(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess project risks and create mitigation plan."""
        project_plan = input_data.get("project_plan", {})
        self.emit_status("Assessing project risks...", "info")

        return {
            "risk_register": [],
            "mitigation_plan": {},
        }

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        # Add planning-specific context
        packet.payload["planning_context"] = {
            "task_graph": artifacts.get("task_graph", {}),
            "milestones": artifacts.get("milestones", []),
            "risk_register": artifacts.get("risk_register", []),
        }
        return packet


def create_planning_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.ANALYTICAL,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> PlanningAgent:
    """Factory function to create a PlanningAgent."""
    return PlanningAgent(agent_id, personality, model_config, signals)