"""
CustomAgent — User-defined custom agents with flexible capabilities.

This module provides the CustomAgent class and CustomAgentBuilder for creating
user-defined agents with custom capabilities, personalities, and system prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


@dataclass
class CustomAgentConfig:
    """Configuration for a custom agent."""
    name: str
    description: str
    system_prompt: str
    personality: AgentPersonality
    capabilities: List[AgentCapability]
    model_config: Dict[str, Any] = field(default_factory=dict)


class CustomAgent(BaseAgent):
    """
    A custom agent defined by the user with flexible capabilities and personality.
    
    Custom agents can be created through the CustomAgentBuilder or directly
    with a CustomAgentConfig.
    """
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        personality: AgentPersonality,
        capabilities: List[AgentCapability],
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        self.name = name
        self.description = description
        
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.CUSTOM,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )
    
    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute custom agent task."""
        self.set_task(task)
        self.set_context(context)
        
        # Custom agents execute based on their system prompt and capabilities
        # This is a base implementation - custom logic would be added via tools
        self.emit_status(f"Custom agent {self.name} executing task: {task.title}", "info")
        
        # Default behavior: return input data as output
        result = {
            "agent": self.name,
            "task": task.title,
            "input": task.input_data,
            "status": "completed",
        }
        
        self.complete_task(result)
        return result
    
    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base
    
    @classmethod
    def from_config(cls, agent_id: str, config: CustomAgentConfig, signals: Any = None) -> CustomAgent:
        """Create a CustomAgent from a configuration object."""
        return cls(
            agent_id=agent_id,
            name=config.name,
            description=config.description,
            system_prompt=config.system_prompt,
            personality=config.personality,
            capabilities=config.capabilities,
            model_config=config.model_config,
            signals=signals,
        )


class CustomAgentBuilder:
    """
    Builder for creating custom agents with fluent API.
    
    Example:
        agent = (CustomAgentBuilder("my-agent")
            .with_name("My Custom Agent")
            .with_description("A custom agent for specific tasks")
            .with_personality(AgentPersonality.CREATIVE)
            .with_capability("custom_cap", "Custom capability", ["tool1"], ["artifact1"])
            .with_system_prompt("You are a custom agent...")
            .build())
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._name = "Custom Agent"
        self._description = "A custom agent"
        self._personality = AgentPersonality.COLLABORATIVE
        self._capabilities: List[AgentCapability] = []
        self._system_prompt = "You are a custom agent."
        self._model_config: Dict[str, Any] = {}
        self._signals: Any = None
    
    def with_name(self, name: str) -> CustomAgentBuilder:
        """Set the agent's display name."""
        self._name = name
        return self
    
    def with_description(self, description: str) -> CustomAgentBuilder:
        """Set the agent's description."""
        self._description = description
        return self
    
    def with_personality(self, personality: AgentPersonality) -> CustomAgentBuilder:
        """Set the agent's personality."""
        self._personality = personality
        return self
    
    def with_capability(
        self,
        name: str,
        description: str,
        tool_names: List[str] = None,
        produces_artifacts: List[str] = None,
        required_context: List[str] = None,
        confidence: float = 1.0,
    ) -> CustomAgentBuilder:
        """Add a capability to the agent."""
        cap = AgentCapability(
            name=name,
            description=description,
            tool_names=tool_names or [],
            required_context=required_context or [],
            produces_artifacts=produces_artifacts or [],
            confidence=confidence,
        )
        self._capabilities.append(cap)
        return self
    
    def with_system_prompt(self, prompt: str) -> CustomAgentBuilder:
        """Set the agent's system prompt."""
        self._system_prompt = prompt
        return self
    
    def with_model_config(self, config: Dict[str, Any]) -> CustomAgentBuilder:
        """Set the agent's model configuration."""
        self._model_config = config
        return self
    
    def with_signals(self, signals: Any) -> CustomAgentBuilder:
        """Set the agent's signals object."""
        self._signals = signals
        return self
    
    def build(self) -> CustomAgent:
        """Build the custom agent."""
        return CustomAgent(
            agent_id=self.agent_id,
            name=self._name,
            description=self._description,
            system_prompt=self._system_prompt,
            personality=self._personality,
            capabilities=self._capabilities,
            model_config=self._model_config,
            signals=self._signals,
        )
    
    def build_config(self) -> CustomAgentConfig:
        """Build a configuration object without creating the agent."""
        return CustomAgentConfig(
            name=self._name,
            description=self._description,
            system_prompt=self._system_prompt,
            personality=self._personality,
            capabilities=self._capabilities,
            model_config=self._model_config,
        )


def create_custom_agent(
    agent_id: str,
    name: str,
    description: str,
    system_prompt: str,
    personality: AgentPersonality,
    capabilities: List[AgentCapability],
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> CustomAgent:
    """Factory function to create a CustomAgent."""
    return CustomAgent(
        agent_id=agent_id,
        name=name,
        description=description,
        system_prompt=system_prompt,
        personality=personality,
        capabilities=capabilities,
        model_config=model_config or {},
        signals=signals,
    )