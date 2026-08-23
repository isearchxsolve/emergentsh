"""NVIDIA NIM primary client with an opt-in OmniRoute failover transport.

NVIDIA NIM remains the primary inference provider.  When explicitly enabled,
OmniRoute is used only after an NIM transport/upstream failure and only with a
configured, measured model route.  Credentials stay in environment variables
and are never written to application state or logs.
"""

from __future__ import annotations

import os
import time
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
DEFAULT_OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1")
DEFAULT_OMNIROUTE_MODELS = (
    "nvidia/nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nvidia/nemotron-3-nano-30b-a3b",
    "nvidia/meta/llama-3.1-8b-instruct",
)


def _configured_omniroute_models() -> List[str]:
    """Return ordered OmniRoute fallback models without accepting empty IDs."""
    raw = os.getenv("OMNIROUTE_FALLBACK_MODELS", "")
    if not raw.strip():
        return list(DEFAULT_OMNIROUTE_MODELS)
    return [model.strip() for model in raw.split(",") if model.strip()]


class AsyncOmniRouteClient:
    """Minimal OpenAI-compatible OmniRoute client with a failure circuit.

    A real completion, not a TCP connect or catalog response, is required to
    reset the circuit. This prevents a saturated local gateway from adding its
    timeout to every failed NIM request.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        models: Optional[List[str]] = None,
        timeout: float = 20.0,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.api_key = (api_key or os.getenv("OMNIROUTE_API_KEY") or "").strip()
        if not self.api_key:
            raise ValueError("OmniRoute API key required. Set OMNIROUTE_API_KEY.")
        self.base_url = (base_url or DEFAULT_OMNIROUTE_BASE_URL).rstrip("/")
        self.models = models or _configured_omniroute_models()
        if not self.models:
            raise ValueError("At least one OmniRoute fallback model is required.")
        self.timeout = timeout
        self.cooldown_seconds = cooldown_seconds
        self._open_until = 0.0
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

    def _ensure_circuit_closed(self) -> None:
        if time.monotonic() < self._open_until:
            remaining = max(1, round(self._open_until - time.monotonic()))
            raise RuntimeError(f"OmniRoute fallback circuit is open for {remaining}s.")

    def _record_failure(self) -> None:
        self._open_until = time.monotonic() + self.cooldown_seconds

    def _record_success(self) -> None:
        self._open_until = 0.0

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Dict[str, Any]:
        self._ensure_circuit_closed()
        candidates = [model] if model else self.models
        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                response = await self._client.post("chat/completions", json={
                    "model": candidate,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                })
                response.raise_for_status()
                body = response.json()
                content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
                if not stream and not content:
                    raise RuntimeError(f"OmniRoute model {candidate} returned no generated content.")
                self._record_success()
                return body
            except Exception as exc:
                last_error = exc
        self._record_failure()
        raise RuntimeError("All configured OmniRoute fallback models failed.") from last_error

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        self._ensure_circuit_closed()
        candidates = [model] if model else self.models
        last_error: Optional[Exception] = None
        for candidate in candidates:
            emitted = False
            try:
                async with self._client.stream("POST", "chat/completions", json={
                    "model": candidate,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            if emitted:
                                self._record_success()
                                return
                            raise RuntimeError(f"OmniRoute model {candidate} returned no generated content.")
                        import json
                        chunk = json.loads(data)
                        delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                        if delta:
                            emitted = True
                            yield delta
                if emitted:
                    self._record_success()
                    return
                raise RuntimeError(f"OmniRoute model {candidate} returned no generated content.")
            except Exception as exc:
                # Never retry another provider after exposing partial output:
                # doing so would duplicate/incoherently splice generated code.
                if emitted:
                    self._record_failure()
                    raise
                last_error = exc
        self._record_failure()
        raise RuntimeError("All configured OmniRoute fallback models failed.") from last_error

    async def list_models(self) -> List[str]:
        self._ensure_circuit_closed()
        response = await self._client.get("models")
        response.raise_for_status()
        return [item["id"] for item in response.json().get("data", []) if item.get("id")]

    async def health_check(self) -> Dict[str, Any]:
        """Probe one actual short completion; catalog availability is insufficient."""
        try:
            response = await self.chat_completion(
                messages=[{"role": "user", "content": "Reply with exactly: healthy"}],
                max_tokens=8,
                temperature=0,
            )
            content = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            return {"ready": bool(content.strip()), "live": bool(content.strip()), "model": self.models[0]}
        except Exception as exc:
            return {"ready": False, "live": False, "error": str(exc)}


class AsyncNIMClient:
    """Async NVIDIA NIM client with guarded, opt-in OmniRoute failover."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 120.0,
        enable_omniroute_fallback: Optional[bool] = None,
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
        fallback_enabled = (
            os.getenv("OMNIROUTE_FALLBACK_ENABLED", "false").lower() in {"true", "1", "yes"}
            if enable_omniroute_fallback is None
            else enable_omniroute_fallback
        )
        self._fallback: Optional[AsyncOmniRouteClient] = None
        if fallback_enabled:
            try:
                self._fallback = AsyncOmniRouteClient()
            except ValueError:
                # An enabled fallback without a credential is operationally
                # equivalent to no fallback. NIM remains usable and errors
                # should retain the primary provider's root cause.
                self._fallback = None

    async def close(self) -> None:
        await self._client.aclose()
        if self._fallback:
            await self._fallback.close()

    async def _fallback_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        primary_error: Exception,
    ) -> Dict[str, Any]:
        if not self._fallback:
            raise primary_error
        return await self._fallback.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

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
        try:
            resp = await self._client.post("chat/completions", json=body)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as primary_error:
            return await self._fallback_completion(messages, temperature, max_tokens, primary_error)

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
        emitted = False
        try:
            async with self._client.stream("POST", "chat/completions", json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        import json
                        chunk = json.loads(data)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        )
                        if delta:
                            emitted = True
                            yield delta
                    except Exception:
                        continue
        except (httpx.HTTPError, ValueError) as primary_error:
            if emitted or not self._fallback:
                raise
            async for delta in self._fallback.chat_stream(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield delta

    async def list_models(self) -> List[str]:
        resp = await self._client.get("models")
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]

    async def health_check(self) -> Dict[str, Any]:
        primary: Dict[str, Any]
        try:
            models = await self.list_models()
            primary = {"ready": True, "live": True, "models": models[:5]}
        except Exception as e:
            primary = {"ready": False, "live": False, "error": str(e)}
        if self._fallback:
            primary["omniroute_fallback"] = await self._fallback.health_check()
        return primary


def get_nim_client() -> AsyncNIMClient:
    """Factory used by FastAPI dependency injection."""
    return AsyncNIMClient()
