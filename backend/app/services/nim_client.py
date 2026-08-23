"""
NVIDIA NIM client service used by the FastAPI backend.

All generative / reasoning calls for the Emergent.sh clone must go through
this module.  No other LLM providers are permitted.
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

# Prefer the shared root client when available
try:
    from backend.nim_client import NIMClient as SyncNIMClient, NIMConfig
except ImportError:
    try:
        from nim_client import NIMClient as SyncNIMClient, NIMConfig  # type: ignore
    except ImportError:
        SyncNIMClient = None  # type: ignore
        NIMConfig = None  # type: ignore


DEFAULT_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
DEFAULT_MODEL = os.getenv("NIM_DEFAULT_MODEL", "meta/llama-3.1-8b-instruct")


class AsyncNIMClient:
    """Async OpenAI-compatible client pointed exclusively at NVIDIA NIM."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("NIM_API_KEY")
            or os.getenv("NVIDIA_API_KEY")
            or os.getenv("NGC_API_KEY")
            or ""
        ).strip()
        if not self.api_key:
            raise ValueError(
                "NVIDIA NIM API key required. Set NIM_API_KEY or NVIDIA_API_KEY."
            )
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.default_model = default_model or DEFAULT_MODEL
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Dict[str, Any]:
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        # Keep requests relative to base_url.  A leading slash makes HTTPX drop
        # the configured /v1 path and sends NIM requests to the wrong endpoint.
        resp = await self._client.post("chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Yield content deltas from a streaming NIM completion."""
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with self._client.stream("POST", "chat/completions", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    import json
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

    async def list_models(self) -> List[str]:
        resp = await self._client.get("models")
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]

    async def health_check(self) -> Dict[str, Any]:
        try:
            models = await self.list_models()
            return {"ready": True, "live": True, "models": models[:5]}
        except Exception as e:
            return {"ready": False, "live": False, "error": str(e)}


def get_nim_client() -> AsyncNIMClient:
    """Factory used by FastAPI dependency injection."""
    return AsyncNIMClient()
