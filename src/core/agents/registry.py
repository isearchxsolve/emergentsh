"""
AgentRegistry — Central registry for agent types and instances.

Provides lookup, registration, and factory access for all specialized agents
in the emergent.sh multi-agent orchestration platform.
"""

from typing import Dict, List, Optional, Type
from .base import BaseAgent, AgentRole


class AgentRegistry:
    """Central registry mapping agent roles to concrete agent classes."""

    def __init__(self) -> None:
        self._classes: Dict[AgentRole, Type[BaseAgent]] = {}
        self._instances: Dict[str, BaseAgent] = {}

    def register(self, role: AgentRole, agent_cls: Type[BaseAgent]) -> None:
        """Register an agent class for a given role."""
        self._classes[role] = agent_cls

    def get_class(self, role: AgentRole) -> Optional[Type[BaseAgent]]:
        """Look up the registered agent class for a role."""
        return self._classes.get(role)

    def register_instance(self, agent_id: str, agent: BaseAgent) -> None:
        """Register a live agent instance by id."""
        self._instances[agent_id] = agent

    def get_instance(self, agent_id: str) -> Optional[BaseAgent]:
        """Retrieve a live agent instance by id."""
        return self._instances.get(agent_id)

    def list_roles(self) -> List[AgentRole]:
        """Return all registered roles."""
        return list(self._classes.keys())


_REGISTRY: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Return the singleton AgentRegistry, initializing on first use."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = AgentRegistry()
    return _REGISTRY
