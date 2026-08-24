"""OpenAI-compatible inference transports for NVIDIA NIM and OmniRoute.

OmniRoute can be selected as the primary scalable gateway, allowing it to own
NVIDIA key rotation and upstream capacity. Direct NIM remains available for
development or emergency operation. Credentials stay in environment variables
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
# 20130 is NeonBuild's canonical local OmniRoute listener. 20128 was the
# legacy wrapper port and can remain occupied by an unrelated protected
# process; defaulting to it recreates a split-brain gateway after restart.
DEFAULT_OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:20130/v1")
# These are OmniRoute *routes*, rather than a pinned NVIDIA model. Each route
# is a provider-aware policy managed by OmniRoute, so it can use its ordered
# upstream providers and credentials without NeonBuild knowing any provider
# secrets. Keep the list deliberately short and proven: it is both the default
# gateway health probe and the last-resort route fallback.
DEFAULT_OMNIROUTE_MODELS = (
    "auto/best-coding",
    "auto/best-reasoning",
)

# Stage routing lets the gateway apply the right cross-provider policy to the
# work at hand. Operators may override any value with, for example,
# OMNIROUTE_FRONTEND_ROUTE=fusion-coder, without a code deployment. A route
# can also be a concrete model where an operator intentionally wants that.
DEFAULT_OMNIROUTE_ROUTES_BY_STAGE = {
    "planner": "auto/best-reasoning",
    "designer": "auto/best-reasoning",
    "frontend": "auto/best-coding",
    "backend": "auto/best-coding",
    "integration": "auto/best-coding",
    "preview": "auto/best-coding",
    "qa": "auto/best-coding",
    "devops": "auto/best-coding",
}


def _configured_omniroute_models() -> List[str]:
    """Return ordered gateway route fallbacks without accepting empty IDs."""
    raw = os.getenv("OMNIROUTE_FALLBACK_MODELS", "")
    if not raw.strip():
        return list(DEFAULT_OMNIROUTE_MODELS)
    return [model.strip() for model in raw.split(",") if model.strip()]


def configured_omniroute_route(stage: str) -> str:
    """Return the OmniRoute route selected for a NeonBuild pipeline stage.

    The stage value is intentionally a string so this module remains usable by
    the transport layer without importing the pipeline's enum. Unknown stages
    use the general coding route rather than accidentally pinning a provider.
    """
    normalized_stage = stage.strip().lower()
    default = DEFAULT_OMNIROUTE_ROUTES_BY_STAGE.get(
        normalized_stage, DEFAULT_OMNIROUTE_MODELS[0]
    )
    env_name = f"OMNIROUTE_{normalized_stage.upper()}_ROUTE"
    return os.getenv(env_name, default).strip() or default


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
        timeout: Optional[float] = None,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.api_key = (api_key or os.getenv("OMNIROUTE_API_KEY") or "").strip()
        if not self.api_key:
            raise ValueError("OmniRoute API key required. Set OMNIROUTE_API_KEY.")
        self.base_url = (base_url or DEFAULT_OMNIROUTE_BASE_URL).rstrip("/")
        self.models = models or _configured_omniroute_models()
        if not self.models:
            raise ValueError("At least one OmniRoute fallback model is required.")
        # Composite routes may need to advance between upstream providers or
        # produce a long planning/code response. A 20-second gateway timeout
        # turns normal generation latency into avoidable repair loops.
        self.timeout = timeout if timeout is not None else float(
            os.getenv("OMNIROUTE_TIMEOUT_SECONDS", "600")
        )
        self.cooldown_seconds = cooldown_seconds
        self._open_until = 0.0
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self.timeout,
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

    def _candidate_routes(self, model: Optional[str]) -> List[str]:
        """Try the requested route first, then the gateway's safe fallbacks."""
        candidates = [model] if model else []
        candidates.extend(self.models)
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))

    @staticmethod
    def _safe_route_error(candidate: str, exc: Exception) -> str:
        """Keep route diagnostics actionable without exposing credentials/body data."""
        if isinstance(exc, httpx.HTTPStatusError):
            return f"{candidate} (HTTP {exc.response.status_code})"
        return f"{candidate} ({type(exc).__name__})"

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Dict[str, Any]:
        self._ensure_circuit_closed()
        candidates = self._candidate_routes(model)
        last_error: Optional[Exception] = None
        route_errors: List[str] = []
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
                route_errors.append(self._safe_route_error(candidate, exc))
        self._record_failure()
        details = ", ".join(route_errors) or "no route diagnostics"
        raise RuntimeError(f"All configured OmniRoute routes failed: {details}.") from last_error

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        self._ensure_circuit_closed()
        candidates = self._candidate_routes(model)
        last_error: Optional[Exception] = None
        route_errors: List[str] = []
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
                    # Some OmniRoute composite policies intentionally return a
                    # complete OpenAI JSON payload even when stream=true. That
                    # is still a valid completion; surface it as one delta
                    # instead of falsely marking the route as empty and
                    # failing an otherwise healthy pipeline stage.
                    content_type = response.headers.get("content-type", "").lower()
                    if "application/json" in content_type:
                        import json
                        body = json.loads((await response.aread()).decode("utf-8"))
                        content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
                        if content:
                            emitted = True
                            yield content
                            self._record_success()
                            return
                        raise RuntimeError(f"OmniRoute model {candidate} returned no generated content.")
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
                route_errors.append(self._safe_route_error(candidate, exc))
        self._record_failure()
        details = ", ".join(route_errors) or "no route diagnostics"
        raise RuntimeError(f"All configured OmniRoute routes failed: {details}.") from last_error

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


def configured_inference_provider() -> str:
    """Resolve the provider without silently downgrading a configured gateway."""
    requested = os.getenv("INFERENCE_PROVIDER", "auto").strip().lower()
    if requested not in {"auto", "omniroute", "nim"}:
        raise ValueError("INFERENCE_PROVIDER must be auto, omniroute, or nim")
    if requested == "auto":
        return "omniroute" if os.getenv("OMNIROUTE_API_KEY", "").strip() else "nim"
    return requested


def get_inference_client():
    """Create the configured primary transport.

    In OmniRoute mode individual NVIDIA keys are deliberately neither accepted
    nor inspected; rotation belongs to the gateway.
    """
    provider = configured_inference_provider()
    if provider == "omniroute":
        return AsyncOmniRouteClient()
    return AsyncNIMClient()
