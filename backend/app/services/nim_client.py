"""OpenAI-compatible inference transports with OmniRoute as the consumer boundary.

The SaaS pipeline must never select an upstream provider. OmniRoute owns
provider credentials, route selection, sessions, and capacity; the legacy NIM
client remains importable only for isolated developer tests and is not exposed
by the application inference factory.
"""

from __future__ import annotations

import asyncio
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


CANONICAL_OMNIROUTE_BASE_URL = "http://127.0.0.1:8190/v1"
CANONICAL_OMNIROUTE_CHAT_MODEL = "session-pool/auto"

DEFAULT_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
DEFAULT_MODEL = os.getenv("NIM_DEFAULT_MODEL", "meta/llama-3.1-8b-instruct")
# The application boundary is the task-owned session-pool shim.  The old
# 20128/20130 listeners are supply-side or diagnostic surfaces; selecting one
# here would bypass the consumer contract and recreate split-brain routing.
DEFAULT_OMNIROUTE_BASE_URL = CANONICAL_OMNIROUTE_BASE_URL
# These are OmniRoute *routes*, rather than a pinned NVIDIA model. Each route
# is a provider-aware policy managed by OmniRoute, so it can use its ordered
# upstream providers and credentials without NeonBuild knowing any provider
# secrets. Keep the list deliberately short and proven: it is both the default
# gateway health probe and the last-resort route fallback.
DEFAULT_OMNIROUTE_MODELS = (
    CANONICAL_OMNIROUTE_CHAT_MODEL,
)

# Stage names remain for compatibility with the pipeline's policy interface,
# but every application stage enters the same provider-aware consumer route.
# A stage-specific model override would bypass that boundary, so it is rejected
# at request/startup configuration time below.
DEFAULT_OMNIROUTE_ROUTES_BY_STAGE = {
    "planner": CANONICAL_OMNIROUTE_CHAT_MODEL,
    "designer": CANONICAL_OMNIROUTE_CHAT_MODEL,
    "frontend": CANONICAL_OMNIROUTE_CHAT_MODEL,
    "backend": CANONICAL_OMNIROUTE_CHAT_MODEL,
    "integration": CANONICAL_OMNIROUTE_CHAT_MODEL,
    "preview": CANONICAL_OMNIROUTE_CHAT_MODEL,
    "qa": CANONICAL_OMNIROUTE_CHAT_MODEL,
    "devops": CANONICAL_OMNIROUTE_CHAT_MODEL,
}


def configured_omniroute_base_url() -> str:
    """Return the one allowed application inference base URL.

    A gateway URL is a security and routing boundary, not a cosmetic setting:
    allowing ``localhost`` or an old port sends traffic around the session-pool
    shim.  The value is checked at runtime (rather than only at import time) so
    startup and tests observe the same configuration.
    """

    configured = os.getenv("OMNIROUTE_BASE_URL", CANONICAL_OMNIROUTE_BASE_URL).strip().rstrip("/")
    if configured != CANONICAL_OMNIROUTE_BASE_URL:
        raise ValueError(
            "EmergentSH must use the canonical consumer endpoint "
            f"{CANONICAL_OMNIROUTE_BASE_URL}; received {configured!r}"
        )
    return CANONICAL_OMNIROUTE_BASE_URL


def _omniroute_streaming_enabled() -> bool:
    """Return whether the gateway should use token-event streaming.

    OmniRoute's streaming responses contain reliable terminal completion
    events, and stopping at that event preserves complete content while
    avoiding providers that leave the HTTP connection open afterwards. The
    non-streaming mode remains available for gateways that only expose JSON
    completions by setting OMNIROUTE_STREAMING_ENABLED=false.
    """
    return os.getenv("OMNIROUTE_STREAMING_ENABLED", "true").strip().lower() in {
        "true", "1", "yes", "on"
    }


def _configured_omniroute_models() -> List[str]:
    """Return the canonical gateway route without accepting empty/alternate IDs."""
    raw = os.getenv("OMNIROUTE_FALLBACK_MODELS", "")
    if not raw.strip():
        return list(DEFAULT_OMNIROUTE_MODELS)
    models = [model.strip() for model in raw.split(",") if model.strip()]
    if models != [CANONICAL_OMNIROUTE_CHAT_MODEL]:
        raise ValueError(
            "OMNIROUTE_FALLBACK_MODELS must contain only "
            f"{CANONICAL_OMNIROUTE_CHAT_MODEL!r}"
        )
    return models


def configured_omniroute_route(stage: str) -> str:
    """Return the OmniRoute route selected for a NeonBuild pipeline stage.

    The stage value is intentionally a string so this module remains usable by
    the transport layer without importing the pipeline's enum. Unknown stages
    still use the one canonical consumer route rather than pinning a provider.
    """
    normalized_stage = stage.strip().lower()
    default = DEFAULT_OMNIROUTE_ROUTES_BY_STAGE.get(normalized_stage, CANONICAL_OMNIROUTE_CHAT_MODEL)
    env_name = f"OMNIROUTE_{normalized_stage.upper()}_ROUTE"
    selected = os.getenv(env_name, default).strip() or default
    if selected != CANONICAL_OMNIROUTE_CHAT_MODEL:
        raise ValueError(
            f"{env_name} must remain {CANONICAL_OMNIROUTE_CHAT_MODEL!r}; "
            f"received {selected!r}"
        )
    return selected


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
        selected_base_url = (base_url or configured_omniroute_base_url()).rstrip("/")
        if selected_base_url != CANONICAL_OMNIROUTE_BASE_URL:
            raise ValueError(
                "AsyncOmniRouteClient must use the canonical consumer endpoint "
                f"{CANONICAL_OMNIROUTE_BASE_URL}; received {selected_base_url!r}"
            )
        self.base_url = CANONICAL_OMNIROUTE_BASE_URL
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
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
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
                # httpx's read timeout is deliberately reset by every byte
                # received. A gateway can therefore keep a response alive
                # forever with heartbeats or partial data. The agent contract
                # is a real *total* per-completion deadline, so enforce it
                # independently of transport-level read timeouts.
                async with asyncio.timeout(self.timeout):
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
        # Pipeline stages are batch operations: validation waits for a complete
        # answer, but OmniRoute's terminal SSE event lets us capture that answer
        # without waiting for a provider to close a lingering connection.
        if not _omniroute_streaming_enabled():
            body = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
            content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
            if not content:
                raise RuntimeError("OmniRoute returned no generated content for batch completion.")
            yield content
            return

        self._ensure_circuit_closed()
        candidates = self._candidate_routes(model)
        last_error: Optional[Exception] = None
        route_errors: List[str] = []
        for candidate in candidates:
            emitted = False
            try:
                # Apply the same wall-clock completion budget as batch mode.
                # HTTPX's read timeout alone resets whenever a heartbeat or
                # partial token arrives and cannot enforce this guarantee.
                async with asyncio.timeout(self.timeout):
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
                            choice = (chunk.get("choices") or [{}])[0]
                            delta = (choice.get("delta") or {}).get("content")
                            if delta:
                                emitted = True
                                yield delta
                            # A number of providers send finish_reason but do
                            # not send [DONE] or close promptly. Completion is
                            # authoritative, so do not keep the stage waiting.
                            if choice.get("finish_reason"):
                                if emitted:
                                    self._record_success()
                                    return
                                raise RuntimeError(f"OmniRoute model {candidate} returned no generated content.")
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
    """Retired FastAPI factory kept only as an explicit failure for old callers."""
    raise RuntimeError("direct NVIDIA NIM is retired for EmergentSH application execution; use get_inference_client()")


def configured_inference_provider() -> str:
    """Return the sole supported SaaS inference transport or fail closed.

    ``auto`` is retained as a harmless compatibility spelling, but it no
    longer means "choose a direct provider when a gateway variable is absent".
    """
    requested = os.getenv("INFERENCE_PROVIDER", "omniroute").strip().lower()
    runtime = os.getenv("APP_ENV", "development").strip().lower()
    if runtime in {"production", "prod"} and requested != "omniroute":
        raise ValueError(
            "EmergentSH production inference must use INFERENCE_PROVIDER=omniroute"
        )
    if requested not in {"auto", "omniroute"}:
        raise ValueError("EmergentSH production inference must use INFERENCE_PROVIDER=omniroute")
    configured_omniroute_base_url()
    return "omniroute"


def get_inference_client():
    """Create the configured primary transport.

    In OmniRoute mode individual NVIDIA keys are deliberately neither accepted
    nor inspected; rotation belongs to the gateway.
    """
    configured_inference_provider()
    return AsyncOmniRouteClient()
