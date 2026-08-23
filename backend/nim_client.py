"""
NVIDIA NIM client for the EmergentSH agent pipeline.

Provides a synchronous HTTP interface (chat_completion / get_models) plus an
async streaming interface (chat_stream) used by backend.agent_pipeline agents.
All generative calls route exclusively through NVIDIA NIM endpoints.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

DEFAULT_BASE_URL = "https://api.nv.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/llama-3.1-nim-70b"


@dataclass
class NIMConfig:
    """Configuration for the NIM client."""

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    default_model: str = DEFAULT_MODEL
    timeout: float = 30
    max_tokens: int = 4096
    temperature: float = 0.7

    @classmethod
    def from_env(cls) -> "NIMConfig":
        return cls(
            api_key=(
                os.getenv("NIM_API_KEY")
                or os.getenv("NVIDIA_API_KEY")
                or os.getenv("NGC_API_KEY")
                or ""
            ),
            base_url=os.getenv("NIM_BASE_URL", DEFAULT_BASE_URL),
            default_model=os.getenv("NIM_DEFAULT_MODEL", DEFAULT_MODEL),
        )


class NIMClient:
    """OpenAI-compatible client pointed exclusively at NVIDIA NIM.

    Accepts either keyword arguments (api_key=..., base_url=...) or a single
    NIMConfig as the first positional argument.
    """

    def __init__(
        self,
        api_key: Optional[Any] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> None:
        if isinstance(api_key, NIMConfig):
            config = api_key
            self.api_key = config.api_key
            self.base_url = (base_url or config.base_url).rstrip("/")
            self.default_model = default_model or config.default_model
            self.timeout = timeout if timeout is not None else config.timeout
            self.max_tokens = max_tokens if max_tokens is not None else config.max_tokens
            self.temperature = temperature if temperature is not None else config.temperature
        else:
            if api_key is None:
                api_key = (
                    os.getenv("NIM_API_KEY")
                    or os.getenv("NVIDIA_API_KEY")
                    or os.getenv("NGC_API_KEY")
                    or ""
                )
            self.api_key = api_key
            self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
            self.default_model = default_model or DEFAULT_MODEL
            self.timeout = timeout if timeout is not None else 30
            self.max_tokens = max_tokens if max_tokens is not None else 4096
            self.temperature = temperature if temperature is not None else 0.7

        if not str(self.api_key).strip():
            raise ValueError(
                "NVIDIA NIM API key required. Set NIM_API_KEY or NVIDIA_API_KEY."
            )

    # ------------------------------------------------------------------
    # Synchronous HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        resp = httpx.post(
            f"{self.base_url}{path}",
            json=body,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str) -> Dict[str, Any]:
        resp = httpx.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Synchronous API
    # ------------------------------------------------------------------

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        return self._post("/chat/completions", body)

    def get_models(self) -> List[str]:
        data = self._get("/models")
        return [m["id"] for m in data.get("data", [])]

    # ------------------------------------------------------------------
    # Async streaming API (used by backend.agent_pipeline)
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Yield content deltas from a streaming NIM completion."""
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=max(self.timeout, 120.0)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=body,
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        )
                        if delta:
                            yield delta
                    except Exception:
                        continue
