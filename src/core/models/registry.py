"""
Model Registry & Marketplace — manages LLM models from various providers.

Supports: NVIDIA NIM, OpenRouter, Anthropic, OpenAI, local (Ollama), custom endpoints.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from ..workspace import WorkspaceManager, get_workspace


# ════════════════════════════════════════════════════════════════════════════
# Enums & Data Models
# ════════════════════════════════════════════════════════════════════════════

class ModelProvider(str, Enum):
    """Supported model providers."""
    NVIDIA_NIM = "nvidia_nim"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class ModelCapability(str, Enum):
    """Model capabilities."""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    REASONING = "reasoning"  # Extended thinking/reasoning modes


@dataclass
class ModelInfo:
    """Model metadata and capabilities."""
    id: str  # Unique identifier (e.g., "nvidia/nemotron-3-ultra")
    name: str  # Display name
    provider: ModelProvider
    provider_model_id: str  # Provider-specific model ID
    
    # Capabilities
    capabilities: Set[ModelCapability] = field(default_factory=set)
    context_window: int = 4096
    max_output_tokens: int = 4096
    
    # Pricing (per 1M tokens)
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    
    # Features
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    reasoning_effort_levels: List[str] = field(default_factory=list)  # low, medium, high
    
    # Metadata
    description: str = ""
    release_date: Optional[str] = None
    is_deprecated: bool = False
    is_free: bool = False
    
    # Provider-specific config
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider.value,
            "provider_model_id": self.provider_model_id,
            "capabilities": [c.value for c in self.capabilities],
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "input_price_per_million": self.input_price_per_million,
            "output_price_per_million": self.output_price_per_million,
            "supports_streaming": self.supports_streaming,
            "supports_function_calling": self.supports_function_calling,
            "supports_vision": self.supports_vision,
            "supports_reasoning": self.supports_reasoning,
            "reasoning_effort_levels": self.reasoning_effort_levels,
            "description": self.description,
            "release_date": self.release_date,
            "is_deprecated": self.is_deprecated,
            "is_free": self.is_free,
            "base_url": self.base_url,
            "api_version": self.api_version,
            "extra_params": self.extra_params,
        }
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        return cls(
            id=data["id"],
            name=data["name"],
            provider=ModelProvider(data["provider"]),
            provider_model_id=data["provider_model_id"],
            capabilities={ModelCapability(c) for c in data.get("capabilities", [])},
            context_window=data.get("context_window", 4096),
            max_output_tokens=data.get("max_output_tokens", 4096),
            input_price_per_million=data.get("input_price_per_million", 0.0),
            output_price_per_million=data.get("output_price_per_million", 0.0),
            supports_streaming=data.get("supports_streaming", True),
            supports_function_calling=data.get("supports_function_calling", False),
            supports_vision=data.get("supports_vision", False),
            supports_reasoning=data.get("supports_reasoning", False),
            reasoning_effort_levels=data.get("reasoning_effort_levels", []),
            description=data.get("description", ""),
            release_date=data.get("release_date"),
            is_deprecated=data.get("is_deprecated", False),
            is_free=data.get("is_free", False),
            base_url=data.get("base_url"),
            api_version=data.get("api_version"),
            extra_params=data.get("extra_params", {}),
        )


# ════════════════════════════════════════════════════════════════════════════
# Model Registry
# ════════════════════════════════════════════════════════════════════════════

class ModelRegistry:
    """
    Central registry for all available models.
    
    Features:
    - Built-in model catalog from major providers
    - Custom model registration
    - Model filtering by capabilities
    - Persistence to workspace
    """
    
    def __init__(self, workspace: Optional[WorkspaceManager] = None):
        self._workspace = workspace or get_workspace()
        self._models: Dict[str, ModelInfo] = {}
        self._lock = threading.Lock()
        self._initialize_builtin_models()
        self._load_custom_models()
    
    # ----------------------------------------------------------------------
    # Built-in Model Catalog
    # ----------------------------------------------------------------------
    
    def _initialize_builtin_models(self) -> None:
        """Register built-in models from major providers."""
        
        # NVIDIA NIM Models
        self._register(ModelInfo(
            id="nvidia/nemotron-3-ultra",
            name="Nemotron 3 Ultra",
            provider=ModelProvider.NVIDIA_NIM,
            provider_model_id="nvidia/nemotron-3-ultra",
            capabilities={ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING},
            context_window=128000,
            max_output_tokens=8192,
            input_price_per_million=0.0,  # Free tier available
            output_price_per_million=0.0,
            supports_reasoning=True,
            reasoning_effort_levels=["low", "medium", "high"],
            base_url="https://integrate.api.nvidia.com/v1",
            description="NVIDIA's flagship reasoning model with extended thinking",
        ))
        
        self._register(ModelInfo(
            id="nvidia/nemotron-3-ultra-256k",
            name="Nemotron 3 Ultra (256K)",
            provider=ModelProvider.NVIDIA_NIM,
            provider_model_id="nvidia/nemotron-3-ultra-256k",
            capabilities={ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING},
            context_window=256000,
            max_output_tokens=16384,
            input_price_per_million=0.0,
            output_price_per_million=0.0,
            supports_reasoning=True,
            reasoning_effort_levels=["low", "medium", "high"],
            base_url="https://integrate.api.nvidia.com/v1",
            description="Nemotron 3 Ultra with 256K context window",
        ))
        
        self._register(ModelInfo(
            id="nvidia/llama-3.1-nemotron-70b-instruct",
            name="Llama 3.1 Nemotron 70B",
            provider=ModelProvider.NVIDIA_NIM,
            provider_model_id="nvidia/llama-3.1-nemotron-70b-instruct",
            capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING},
            context_window=128000,
            max_output_tokens=8192,
            input_price_per_million=0.0,
            output_price_per_million=0.0,
            base_url="https://integrate.api.nvidia.com/v1",
            description="NVIDIA-tuned Llama 3.1 70B for instruction following",
        ))
        
        self._register(ModelInfo(
            id="nvidia/mistral-7b-instruct-v0.3",
            name="Mistral 7B Instruct v0.3",
            provider=ModelProvider.NVIDIA_NIM,
            provider_model_id="nvidia/mistral-7b-instruct-v0.3",
            capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING},
            context_window=32768,
            max_output_tokens=4096,
            input_price_per_million=0.0,
            output_price_per_million=0.0,
            base_url="https://integrate.api.nvidia.com/v1",
            description="Fast and efficient 7B instruct model",
        ))
        
        # OpenRouter Models (Free tier)
        self._register(ModelInfo(
            id="openrouter/nvidia/nemotron-3-ultra:free",
            name="Nemotron 3 Ultra (Free)",
            provider=ModelProvider.OPENROUTER,
            provider_model_id="nvidia/nemotron-3-ultra:free",
            capabilities={ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING},
            context_window=128000,
            max_output_tokens=8192,
            is_free=True,
            supports_reasoning=True,
            reasoning_effort_levels=["low", "medium", "high"],
            base_url="https://openrouter.ai/api/v1",
            description="Free tier Nemotron 3 Ultra via OpenRouter",
        ))
        
        self._register(ModelInfo(
            id="openrouter/qwen/qwen-2.5-coder-32b-instruct:free",
            name="Qwen 2.5 Coder 32B (Free)",
            provider=ModelProvider.OPENROUTER,
            provider_model_id="qwen/qwen-2.5-coder-32b-instruct:free",
            capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.COMPLETION},
            context_window=32768,
            max_output_tokens=8192,
            is_free=True,
            supports_function_calling=True,
            base_url="https://openrouter.ai/api/v1",
            description="Excellent coding model, free via OpenRouter",
        ))
        
        self._register(ModelInfo(
            id="openrouter/meta-llama/llama-3.1-405b-instruct:free",
            name="Llama 3.1 405B Instruct (Free)",
            provider=ModelProvider.OPENROUTER,
            provider_model_id="meta-llama/llama-3.1-405b-instruct:free",
            capabilities={ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING},
            context_window=128000,
            max_output_tokens=8192,
            is_free=True,
            supports_reasoning=True,
            base_url="https://openrouter.ai/api/v1",
            description="Meta's largest open model, free via OpenRouter",
        ))
        
        # Anthropic Models
        self._register(ModelInfo(
            id="anthropic/claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet",
            provider=ModelProvider.ANTHROPIC,
            provider_model_id="claude-3-5-sonnet-20241022",
            capabilities={ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION},
            context_window=200000,
            max_output_tokens=8192,
            input_price_per_million=3.0,
            output_price_per_million=15.0,
            supports_reasoning=True,
            supports_vision=True,
            supports_function_calling=True,
            base_url="https://api.anthropic.com",
            description="Anthropic's most capable model with vision support",
        ))
        
        self._register(ModelInfo(
            id="anthropic/claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            provider=ModelProvider.ANTHROPIC,
            provider_model_id="claude-3-5-haiku-20241022",
            capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION},
            context_window=200000,
            max_output_tokens=8192,
            input_price_per_million=0.8,
            output_price_per_million=4.0,
            supports_vision=True,
            supports_function_calling=True,
            base_url="https://api.anthropic.com",
            description="Fast and affordable Claude 3.5 model",
        ))
        
        # OpenAI Models
        self._register(ModelInfo(
            id="openai/gpt-4o",
            name="GPT-4o",
            provider=ModelProvider.OPENAI,
            provider_model_id="gpt-4o",
            capabilities={ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION},
            context_window=128000,
            max_output_tokens=16384,
            input_price_per_million=2.5,
            output_price_per_million=10.0,
            supports_reasoning=True,
            supports_vision=True,
            supports_function_calling=True,
            base_url="https://api.openai.com/v1",
            description="OpenAI's flagship multimodal model",
        ))
        
        self._register(ModelInfo(
            id="openai/gpt-4o-mini",
            name="GPT-4o Mini",
            provider=ModelProvider.OPENAI,
            provider_model_id="gpt-4o-mini",
            capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION},
            context_window=128000,
            max_output_tokens=16384,
            input_price_per_million=0.15,
            output_price_per_million=0.6,
            supports_vision=True,
            supports_function_calling=True,
            base_url="https://api.openai.com/v1",
            description="Fast and affordable GPT-4o variant",
        ))
        
        # Ollama Local Models
        self._register(ModelInfo(
            id="ollama/llama3.1:70b",
            name="Llama 3.1 70B (Local)",
            provider=ModelProvider.OLLAMA,
            provider_model_id="llama3.1:70b",
            capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.REASONING},
            context_window=128000,
            max_output_tokens=8192,
            is_free=True,
            supports_reasoning=True,
            supports_function_calling=True,
            base_url="http://localhost:11434/v1",
            description="Meta's Llama 3.1 70B running locally via Ollama",
        ))
        
        self._register(ModelInfo(
            id="ollama/llama3.1:8b",
            name="Llama 3.1 8B (Local)",
            provider=ModelProvider.OLLAMA,
            provider_model_id="llama3.1:8b",
            capabilities={ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING},
            context_window=128000,
            max_output_tokens=8192,
            is_free=True,
            supports_function_calling=True,
            base_url="http://localhost:11434/v1",
            description="Lightweight Llama 3.1 8B for local inference",
        ))
        
        self._register(ModelInfo(
            id="ollama/codellama:7b",
            name="CodeLlama 7B (Local)",
            provider=ModelProvider.OLLAMA,
            provider_model_id="codellama:7b",
            capabilities={ModelCapability.COMPLETION, ModelCapability.CHAT},
            context_window=16384,
            max_output_tokens=4096,
            is_free=True,
            base_url="http://localhost:11434/v1",
            description="Code-specialized Llama model for local development",
        ))
        
        self._register(ModelInfo(
            id="ollama/qwen2.5-coder:32b",
            name="Qwen 2.5 Coder 32B (Local)",
            provider=ModelProvider.OLLAMA,
            provider_model_id="qwen2.5-coder:32b",
            capabilities={ModelCapability.COMPLETION, ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING},
            context_window=32768,
            max_output_tokens=8192,
            is_free=True,
            supports_function_calling=True,
            base_url="http://localhost:11434/v1",
            description="Excellent code model for local development",
        ))
    
    # ----------------------------------------------------------------------
    # Registration & Persistence
    # ----------------------------------------------------------------------
    
    def _register(self, model: ModelInfo) -> None:
        """Register a model in the registry."""
        with self._lock:
            self._models[model.id] = model
    
    def register_custom_model(self, model: ModelInfo) -> None:
        """Register a user-defined custom model."""
        if not model.provider == ModelProvider.CUSTOM:
            model.provider = ModelProvider.CUSTOM
        self._register(model)
        self._persist_custom_models()
    
    def unregister_model(self, model_id: str) -> bool:
        """Unregister a model (only custom models)."""
        with self._lock:
            if model_id in self._models:
                model = self._models[model_id]
                if model.provider == ModelProvider.CUSTOM:
                    del self._models[model_id]
                    self._persist_custom_models()
                    return True
        return False
    
    def _load_custom_models(self) -> None:
        """Load custom models from workspace."""
        # In a full implementation, this would load from the workspace database
        pass
    
    def _persist_custom_models(self) -> None:
        """Save custom models to workspace."""
        # In a full implementation, this would save to the workspace database
        pass
    
    # ----------------------------------------------------------------------
    # Query Methods
    # ----------------------------------------------------------------------
    
    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get a model by ID."""
        return self._models.get(model_id)
    
    def list_models(
        self,
        provider: Optional[ModelProvider] = None,
        capability: Optional[ModelCapability] = None,
        free_only: bool = False,
        include_deprecated: bool = False,
    ) -> List[ModelInfo]:
        """List models with optional filters."""
        with self._lock:
            models = list(self._models.values())
        
        if provider:
            models = [m for m in models if m.provider == provider]
        if capability:
            models = [m for m in models if capability in m.capabilities]
        if free_only:
            models = [m for m in models if m.is_free]
        if not include_deprecated:
            models = [m for m in models if not m.is_deprecated]
        
        return sorted(models, key=lambda m: (m.provider.value, m.name))
    
    def get_models_for_agent(self, agent_role: str) -> List[ModelInfo]:
        """Get recommended models for a specific agent role."""
        role_recommendations = {
            "orchestrator": [ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING],
            "planner": [ModelCapability.REASONING],
            "architect": [ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING],
            "designer": [ModelCapability.VISION, ModelCapability.FUNCTION_CALLING],
            "frontend": [ModelCapability.FUNCTION_CALLING, ModelCapability.VISION],
            "backend": [ModelCapability.FUNCTION_CALLING, ModelCapability.REASONING],
            "integration": [ModelCapability.FUNCTION_CALLING],
            "devops": [ModelCapability.FUNCTION_CALLING],
            "qa": [ModelCapability.FUNCTION_CALLING, ModelCapability.REASONING],
            "docs": [ModelCapability.CHAT],
            "version_control": [ModelCapability.FUNCTION_CALLING],
        }
        
        required_caps = role_recommendations.get(agent_role, [ModelCapability.CHAT])
        models = self.list_models()
        return [m for m in models if all(c in m.capabilities for c in required_caps)]
    
    def estimate_cost(self, model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for a model call."""
        model = self.get_model(model_id)
        if not model:
            return 0.0
        
        input_cost = (prompt_tokens / 1_000_000) * model.input_price_per_million
        output_cost = (completion_tokens / 1_000_000) * model.output_price_per_million
        return input_cost + output_cost


# ════════════════════════════════════════════════════════════════════════════
# Provider Client Factory
# ════════════════════════════════════════════════════════════════════════════

class ModelClientFactory:
    """
    Factory for creating model clients from different providers.
    
    Creates OpenAI-compatible clients for each provider.
    """
    
    def __init__(self, registry: ModelRegistry):
        self._registry = registry
        self._clients: Dict[str, Any] = {}
    
    def create_client(
        self,
        model_id: str,
        api_key: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Create an OpenAI-compatible client for a model.
        
        Returns a client compatible with the OpenAI SDK interface.
        """
        model = self._registry.get_model(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")
        
        # Check cache
        cache_key = f"{model_id}:{api_key or 'default'}"
        if cache_key in self._clients:
            return self._clients[cache_key]
        
        # Create client based on provider
        if model.provider == ModelProvider.NVIDIA_NIM:
            client = self._create_nvidia_client(model, api_key)
        elif model.provider == ModelProvider.OPENROUTER:
            client = self._create_openrouter_client(model, api_key)
        elif model.provider == ModelProvider.ANTHROPIC:
            client = self._create_anthropic_client(model, api_key)
        elif model.provider == ModelProvider.OPENAI:
            client = self._create_openai_client(model, api_key)
        elif model.provider == ModelProvider.OLLAMA:
            client = self._create_ollama_client(model)
        elif model.provider == ModelProvider.CUSTOM:
            client = self._create_custom_client(model, api_key)
        else:
            raise ValueError(f"Unsupported provider: {model.provider}")
        
        self._clients[cache_key] = client
        return client
    
    def _create_nvidia_client(self, model: ModelInfo, api_key: Optional[str]) -> Any:
        from openai import OpenAI
        return OpenAI(
            api_key=api_key or os.environ.get("NVIDIA_API_KEY"),
            base_url=model.base_url or "https://integrate.api.nvidia.com/v1",
        )
    
    def _create_openrouter_client(self, model: ModelInfo, api_key: Optional[str]) -> Any:
        from openai import OpenAI
        return OpenAI(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            base_url=model.base_url or "https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://emergentsh.dev",
                "X-Title": "EmergentSH",
            },
        )
    
    def _create_anthropic_client(self, model: ModelInfo, api_key: Optional[str]) -> Any:
        import anthropic
        return anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=model.base_url or "https://api.anthropic.com",
        )
    
    def _create_openai_client(self, model: ModelInfo, api_key: Optional[str]) -> Any:
        from openai import OpenAI
        return OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=model.base_url or "https://api.openai.com/v1",
        )
    
    def _create_ollama_client(self, model: ModelInfo) -> Any:
        from openai import OpenAI
        return OpenAI(
            api_key="ollama",  # Ollama doesn't require auth
            base_url=model.base_url or "http://localhost:11434/v1",
        )
    
    def _create_custom_client(self, model: ModelInfo, api_key: Optional[str]) -> Any:
        from openai import OpenAI
        return OpenAI(
            api_key=api_key or "custom",
            base_url=model.base_url or "http://localhost:8000/v1",
        )


# ════════════════════════════════════════════════════════════════════════════
# Singleton & Convenience
# ════════════════════════════════════════════════════════════════════════════

_REGISTRY: Optional[ModelRegistry] = None
_FACTORY: Optional[ModelClientFactory] = None


def get_model_registry(workspace: Optional[WorkspaceManager] = None) -> ModelRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ModelRegistry(workspace)
    return _REGISTRY


def get_model_factory(workspace: Optional[WorkspaceManager] = None) -> ModelClientFactory:
    global _FACTORY
    if _FACTORY is None:
        _FACTORY = ModelClientFactory(get_model_registry(workspace))
    return _FACTORY


def create_model_client(
    model_id: str,
    api_key: Optional[str] = None,
    workspace: Optional[WorkspaceManager] = None,
) -> Any:
    """Convenience function to create a model client."""
    factory = get_model_factory(workspace)
    return factory.create_client(model_id, api_key=api_key)


# ════════════════════════════════════════════════════════════════════════════
# Model Selector UI Helper
# ════════════════════════════════════════════════════════════════════════════

def get_model_selector_options(registry: Optional[ModelRegistry] = None) -> List[Dict[str, Any]]:
    """Get model options formatted for UI dropdowns."""
    registry = registry or get_model_registry()
    models = registry.list_models(include_deprecated=False)
    
    options = []
    for m in models:
        options.append({
            "value": m.id,
            "label": f"{m.name} ({m.provider.value})",
            "description": m.description,
            "context_window": m.context_window,
            "is_free": m.is_free,
            "capabilities": [c.value for c in m.capabilities],
            "provider": m.provider.value,
        })
    return options


# ════════════════════════════════════════════════════════════════════════════
# Exports
# ════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ModelProvider",
    "ModelCapability",
    "ModelInfo",
    "ModelRegistry",
    "ModelClientFactory",
    "get_model_registry",
    "get_model_factory",
    "create_model_client",
    "get_model_selector_options",
]