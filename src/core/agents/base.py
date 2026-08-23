"""
BaseAgent — Abstract base class for all specialized agents.

Each agent has a distinct role, personality, tool set, and bounded execution context.
Agents communicate through a structured handoff protocol via the orchestration layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable
from pathlib import Path
import json
import uuid
from datetime import datetime


class AgentRole(Enum):
    """Predefined agent roles in the emergent.sh platform."""
    PLANNING = "planning"
    DESIGN = "design"
    FRONTEND = "frontend"
    BACKEND = "backend"
    INTEGRATION = "integration"
    QA = "qa"
    DEVOPS = "devops"
    VERSION_CONTROL = "version_control"
    ARCHITECT = "architect"
    PM = "pm"
    CUSTOM = "custom"


class AgentPersonality(Enum):
    """Agent personality archetypes that influence communication style and decision-making."""
    ANALYTICAL = "analytical"      # Methodical, data-driven, thorough
    CREATIVE = "creative"          # Innovative, exploratory, design-focused
    PRAGMATIC = "pragmatic"        # Practical, results-oriented, efficient
    CAUTIOUS = "cautious"          # Risk-averse, security-focused, thorough testing
    COLLABORATIVE = "collaborative" # Team-oriented, communicative, consensus-building
    AUTONOMOUS = "autonomous"      # Independent, self-directed, decisive


@dataclass
class AgentCapability:
    """A specific capability an agent possesses."""
    name: str
    description: str
    tool_names: List[str] = field(default_factory=list)
    required_context: List[str] = field(default_factory=list)
    produces_artifacts: List[str] = field(default_factory=list)
    confidence: float = 1.0  # 0.0 to 1.0


@dataclass
class AgentContext:
    """Bounded execution context for an agent."""
    agent_id: str
    role: AgentRole
    project_id: str
    task_id: str
    working_directory: Path
    available_tools: Set[str]
    input_artifacts: Dict[str, Any] = field(default_factory=dict)
    output_artifacts: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_task_id: Optional[str] = None
    handoff_history: List[Dict] = field(default_factory=list)


@dataclass
class AgentTask:
    """A task assigned to an agent."""
    id: str
    role: AgentRole
    title: str
    description: str
    priority: int = 0
    dependencies: List[str] = field(default_factory=list)
    assigned_agent_id: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed, blocked
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class HandoffPacket:
    """Structured handoff between agents."""
    from_agent_id: str
    from_role: AgentRole
    to_agent_id: str
    to_role: AgentRole
    task_id: str
    payload: Dict[str, Any]
    artifacts: Dict[str, Any]
    context_summary: str
    requires_approval: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the multi-agent system.
    
    Each agent operates within a bounded context, has a specific role and personality,
    and communicates with other agents through structured handoffs.
    """
    
    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        personality: AgentPersonality,
        capabilities: List[AgentCapability],
        system_prompt: str,
        model_config: Dict[str, Any],
        signals: Any = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.personality = personality
        self.capabilities = {c.name: c for c in capabilities}
        self.system_prompt = system_prompt
        self.model_config = model_config
        self.signals = signals
        self._context: Optional[AgentContext] = None
        self._current_task: Optional[AgentTask] = None
        self._stop_requested = False
        self._tool_registry: Dict[str, Callable] = {}
        
    @property
    def context(self) -> Optional[AgentContext]:
        return self._context
    
    @property
    def current_task(self) -> Optional[AgentTask]:
        return self._current_task
    
    def set_context(self, context: AgentContext) -> None:
        """Set the bounded execution context for this agent."""
        self._context = context
        self._context.available_tools = set(self.get_available_tool_names())
        
    def set_task(self, task: AgentTask) -> None:
        """Assign a task to this agent."""
        self._current_task = task
        task.assigned_agent_id = self.agent_id
        task.status = "running"
        task.started_at = datetime.now()
        
    def get_available_tool_names(self) -> List[str]:
        """Get list of tool names this agent can use."""
        tools = set()
        for cap in self.capabilities.values():
            tools.update(cap.tool_names)
        return list(tools)
    
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function."""
        self._tool_registry[name] = func
        
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a registered tool by name."""
        return self._tool_registry.get(name)
    
    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has a specific capability."""
        return capability_name in self.capabilities
    
    def can_use_tool(self, tool_name: str) -> bool:
        """Check if agent can use a specific tool."""
        return tool_name in self.get_available_tool_names()
    
    @abstractmethod
    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """
        Execute the agent's primary logic for the given task.
        
        Returns output artifacts and metadata for handoff.
        """
        pass
    
    @abstractmethod
    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        pass
    
    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        if not self._context or not self._current_task:
            raise RuntimeError("Agent must have context and task to prepare handoff")
            
        return HandoffPacket(
            from_agent_id=self.agent_id,
            from_role=self.role,
            to_agent_id="",  # Filled by orchestrator
            to_role=to_role,
            task_id=self._current_task.id,
            payload=payload,
            artifacts=artifacts,
            context_summary=self._summarize_context(),
            requires_approval=requires_approval,
        )
    
    def _summarize_context(self) -> str:
        """Generate a concise context summary for handoff."""
        if not self._context or not self._current_task:
            return "No context available"
            
        summary = f"Agent: {self.role.value} ({self.agent_id})\n"
        summary += f"Task: {self._current_task.title}\n"
        summary += f"Project: {self._context.project_id}\n"
        summary += f"Working Dir: {self._context.working_directory}\n"
        summary += f"Artifacts Produced: {list(self._context.output_artifacts.keys())}\n"
        return summary
    
    def request_stop(self) -> None:
        """Request the agent to stop gracefully."""
        self._stop_requested = True
        
    def is_stop_requested(self) -> bool:
        return self._stop_requested
    
    def emit_token(self, token: str, token_type: str = "content") -> None:
        """Emit a token via signals if available."""
        if self.signals:
            if token_type == "reasoning":
                self.signals.token_reasoning.emit(token)
            else:
                self.signals.token_content.emit(token)
    
    def emit_tool_start(self, tool_name: str) -> None:
        if self.signals:
            self.signals.tool_start.emit(tool_name)
    
    def emit_tool_executing(self, tool_name: str, args_json: str) -> None:
        if self.signals:
            self.signals.tool_executing.emit(tool_name, args_json)
    
    def emit_tool_output(self, line: str) -> None:
        if self.signals:
            self.signals.tool_output.emit(line)
    
    def emit_tool_result(self, tool_name: str, result: str) -> None:
        if self.signals:
            self.signals.tool_result.emit(tool_name, result)
    
    def emit_status(self, message: str, level: str = "info") -> None:
        if self.signals:
            if level == "warning":
                self.signals.status_warning.emit(message)
            elif level == "error":
                self.signals.error.emit(message)
            else:
                self.signals.status_info.emit(message)
    
    def complete_task(self, output_data: Dict[str, Any]) -> None:
        """Mark current task as completed with output data."""
        if self._current_task:
            self._current_task.status = "completed"
            self._current_task.output_data = output_data
            self._current_task.completed_at = datetime.now()
            if self._context:
                self._context.output_artifacts.update(output_data)
    
    def fail_task(self, error: str) -> None:
        """Mark current task as failed."""
        if self._current_task:
            self._current_task.status = "failed"
            self._current_task.error = error
            self._current_task.completed_at = datetime.now()


class AgentFactory:
    """Factory for creating agent instances."""
    
    _agent_classes: Dict[AgentRole, type] = {}
    
    @classmethod
    def register(cls, role: AgentRole, agent_class: type) -> None:
        cls._agent_classes[role] = agent_class
    
    @classmethod
    def create(
        cls,
        role: AgentRole,
        agent_id: str,
        personality: AgentPersonality,
        capabilities: List[AgentCapability],
        system_prompt: str,
        model_config: Dict[str, Any],
        signals: Any = None,
    ) -> BaseAgent:
        agent_class = cls._agent_classes.get(role, BaseAgent)
        return agent_class(
            agent_id=agent_id,
            role=role,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config,
            signals=signals,
        )
    
    @classmethod
    def create_custom(
        cls,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        personality: AgentPersonality,
        capabilities: List[AgentCapability],
        model_config: Dict[str, Any],
        signals: Any = None,
    ) -> BaseAgent:
        return CustomAgent(
            agent_id=agent_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            personality=personality,
            capabilities=capabilities,
            model_config=model_config,
            signals=signals,
        )


# Import CustomAgent here to avoid circular imports
from .custom import CustomAgent