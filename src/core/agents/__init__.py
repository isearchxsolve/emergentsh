"""
Multi-Agent System — Core agent definitions, roles, and personalities.

This module defines the agent registry, role system, and base agent classes
that enable emergent.sh's multi-agent orchestration platform.
"""

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket
from .registry import AgentRegistry, get_registry

# Import factory functions
from .planning import create_planning_agent
from .design import create_design_agent
from .frontend import create_frontend_agent
from .backend import create_backend_agent
from .integration import create_integration_agent
from .qa import create_qa_agent
from .devops import create_devops_agent
from .version_control import create_version_control_agent
from .architect import create_architect_agent
from .pm import create_pm_agent
from .designer import create_designer_agent
from .custom import create_custom_agent

# Register default agents lazily on first import
try:
    from .architect import ArchitectAgent
    from .pm import PMAgent
    from .designer import DesignerAgent
    _reg = get_registry()
    _reg.register(AgentRole.ARCHITECT, ArchitectAgent)
    _reg.register(AgentRole.PM, PMAgent)
    _reg.register(AgentRole.DESIGN, DesignerAgent)
except Exception:
    pass

from .planning import PlanningAgent
from .design import DesignAgent
from .frontend import FrontendAgent
from .backend import BackendAgent
from .integration import IntegrationAgent
from .qa import QAAgent
from .devops import DevOpsAgent
from .version_control import VersionControlAgent
from .architect import ArchitectAgent
from .pm import PMAgent
from .designer import DesignerAgent
from .custom import CustomAgent, CustomAgentBuilder

__all__ = [
    "BaseAgent",
    "AgentRole",
    "AgentPersonality",
    "AgentCapability",
    "AgentContext",
    "AgentTask",
    "HandoffPacket",
    "AgentRegistry",
    "get_registry",
    "PlanningAgent",
    "DesignAgent",
    "FrontendAgent",
    "BackendAgent",
    "IntegrationAgent",
    "QAAgent",
    "DevOpsAgent",
    "VersionControlAgent",
    "ArchitectAgent",
    "PMAgent",
    "DesignerAgent",
    "CustomAgent",
    "CustomAgentBuilder",
    # Factory functions
    "create_planning_agent",
    "create_design_agent",
    "create_frontend_agent",
    "create_backend_agent",
    "create_integration_agent",
    "create_qa_agent",
    "create_devops_agent",
    "create_version_control_agent",
    "create_architect_agent",
    "create_pm_agent",
    "create_designer_agent",
    "create_custom_agent",
]