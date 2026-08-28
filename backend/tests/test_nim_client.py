from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from backend.app.services.nim_client import (
    AsyncNIMClient,
    AsyncOmniRouteClient,
    configured_inference_provider,
    configured_omniroute_route,
    get_inference_client,
)


def test_auto_provider_prefers_omniroute_without_nvidia_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFERENCE_PROVIDER", "auto")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "gateway-key")
    for name in ("NIM_API_KEY", "NVIDIA_API_KEY", "NGC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert configured_inference_provider() == "omniroute"
    client = get_inference_client()
    assert isinstance(client, AsyncOmniRouteClient)


def test_explicit_omniroute_never_requires_nvidia_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFERENCE_PROVIDER", "omniroute")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "gateway-key")
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    client = get_inference_client()
    assert isinstance(client, AsyncOmniRouteClient)


def test_omniroute_stage_routes_use_consumer_pool_and_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert configured_omniroute_route("planner") == "chat/session-pool/auto"
    assert configured_omniroute_route("backend") == "chat/session-pool/auto"
    monkeypatch.setenv("OMNIROUTE_BACKEND_ROUTE", "fusion-coder")
    assert configured_omniroute_route("backend") == "fusion-coder"


async def make_client(transport: httpx.MockTransport) -> AsyncNIMClient:
    client = AsyncNIMClient(api_key="test-key", base_url="https://nim.test/v1")
    await client.close()
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        headers={
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        transport=transport,
    )
    return client


async def make_failover_client(
    monkeypatch: pytest.MonkeyPatch,
    primary_transport: httpx.MockTransport,
    fallback_transport: httpx.MockTransport,
) -> AsyncNIMClient:
    """Create a NIM-primary client with isolated mocked OmniRoute transport."""
    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    client = AsyncNIMClient(
        api_key="nim-test-key",
        base_url="https://nim.test/v1",
        enable_omniroute_fallback=True,
    )
    assert client._fallback is not None
    await client._client.aclose()
    await client._fallback._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=primary_transport)
    client._fallback._client = httpx.AsyncClient(
        base_url=client._fallback.base_url,
        transport=fallback_transport,
    )
    return client


def test_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("NIM_API_KEY", "NVIDIA_API_KEY", "NGC_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="API key required"):
        AsyncNIMClient()


@pytest.mark.asyncio
async def test_chat_completion_keeps_v1_base_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.4,
            "max_tokens": 4096,
            "stream": False,
        }
        return httpx.Response(200, json={"id": "chat-1", "choices": []})

    client = await make_client(httpx.MockTransport(handler))
    try:
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "hi"}]
        )
    finally:
        await client.close()

    assert result == {"id": "chat-1", "choices": []}


@pytest.mark.asyncio
async def test_list_models_and_stream_keep_v1_base_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "model-a"}]})
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"!"}}]}\n\n'
            "data: [DONE]\n\n",
        )

    client = await make_client(httpx.MockTransport(handler))
    try:
        assert await client.list_models() == ["model-a"]
        chunks = [
            chunk
            async for chunk in client.chat_stream(
                messages=[{"role": "user", "content": "hi"}]
            )
        ]
    finally:
        await client.close()

    assert chunks == ["Hello", "!"]


@pytest.mark.asyncio
async def test_successful_nim_completion_never_calls_omniroute(monkeypatch: pytest.MonkeyPatch) -> None:
    fallback_calls = 0

    def primary_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "nim result"}}]})

    def fallback_handler(_: httpx.Request) -> httpx.Response:
        nonlocal fallback_calls
        fallback_calls += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "unexpected"}}]})

    client = await make_failover_client(monkeypatch, httpx.MockTransport(primary_handler), httpx.MockTransport(fallback_handler))
    try:
        result = await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
    finally:
        await client.close()

    assert result["choices"][0]["message"]["content"] == "nim result"
    assert fallback_calls == 0


@pytest.mark.asyncio
async def test_nim_failure_uses_next_working_omniroute_route(monkeypatch: pytest.MonkeyPatch) -> None:
    attempted_models: list[str] = []

    def primary_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "NIM unavailable"})

    def fallback_handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        attempted_models.append(model)
        if model == "route-one":
            return httpx.Response(503, json={"error": "route unavailable"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "fallback result"}}]})

    client = await make_failover_client(monkeypatch, httpx.MockTransport(primary_handler), httpx.MockTransport(fallback_handler))
    assert client._fallback is not None
    client._fallback.models = ["route-one", "route-two"]
    try:
        result = await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
    finally:
        await client.close()

    assert result["choices"][0]["message"]["content"] == "fallback result"
    assert attempted_models == ["route-one", "route-two"]


@pytest.mark.asyncio
async def test_omniroute_failure_opens_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": "gateway unavailable"})

    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    client = AsyncOmniRouteClient(models=["route-one"], cooldown_seconds=60)
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(RuntimeError, match="All configured"):
            await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(RuntimeError, match="circuit is open"):
            await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
    finally:
        await client.close()

    assert calls == 1


@pytest.mark.asyncio
async def test_omniroute_completion_enforces_a_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        # A transport can continue producing bytes and thereby avoid a normal
        # HTTP read timeout. The client must still respect its overall budget.
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"choices": [{"message": {"content": "late"}}]})

    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    client = AsyncOmniRouteClient(models=["auto/best-coding"], timeout=0.01, cooldown_seconds=60)
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(RuntimeError, match=r"auto/best-coding \(TimeoutError\)"):
            await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_omniroute_route_error_reports_only_safe_route_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "credential rejected"})

    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    client = AsyncOmniRouteClient(models=["auto/best-coding"], cooldown_seconds=60)
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(RuntimeError, match=r"auto/best-coding \(HTTP 403\)"):
            await client.chat_completion(messages=[{"role": "user", "content": "hi"}])
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_requested_omniroute_route_falls_back_to_another_gateway_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        attempted_models.append(model)
        if model == "auto/best-reasoning":
            return httpx.Response(503, json={"error": "reasoning route unavailable"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "gateway result"}}]})

    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    client = AsyncOmniRouteClient(models=["auto/best-coding"], cooldown_seconds=60)
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    try:
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "hi"}], model="auto/best-reasoning"
        )
    finally:
        await client.close()

    assert result["choices"][0]["message"]["content"] == "gateway result"
    assert attempted_models == ["auto/best-reasoning", "auto/best-coding"]


@pytest.mark.asyncio
async def test_omniroute_stream_accepts_gateway_json_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # OmniRoute can legitimately return a full JSON completion even when
        # the client requests its default terminal-event streaming mode.
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "complete gateway response"}}]},
        )

    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    client = AsyncOmniRouteClient(models=["auto/best-coding"])
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    try:
        chunks = [
            chunk async for chunk in client.chat_stream(
                messages=[{"role": "user", "content": "hi"}], model="auto/best-reasoning"
            )
        ]
    finally:
        await client.close()

    assert chunks == ["complete gateway response"]


@pytest.mark.asyncio
async def test_omniroute_streaming_can_be_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"streamed"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":" response"}}]}\n\n'
            "data: [DONE]\n\n",
        )

    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    monkeypatch.setenv("OMNIROUTE_STREAMING_ENABLED", "true")
    client = AsyncOmniRouteClient(models=["auto/best-coding"])
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    try:
        chunks = [
            chunk async for chunk in client.chat_stream(
                messages=[{"role": "user", "content": "hi"}], model="auto/best-reasoning"
            )
        ]
    finally:
        await client.close()

    assert chunks == ["streamed", " response"]


@pytest.mark.asyncio
async def test_omniroute_stream_stops_at_finish_reason_without_done_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"complete"}}]}\n\n'
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
        )

    monkeypatch.setenv("OMNIROUTE_API_KEY", "omni-test-key")
    client = AsyncOmniRouteClient(models=["auto/best-coding"])
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    try:
        chunks = [
            chunk async for chunk in client.chat_stream(
                messages=[{"role": "user", "content": "hi"}], model="auto/best-reasoning"
            )
        ]
    finally:
        await client.close()

    assert chunks == ["complete"]


@pytest.mark.asyncio
async def test_nim_stream_failure_falls_back_before_any_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def primary_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "NIM unavailable"})

    def fallback_handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "fallback stream"}}]},
        )

    client = await make_failover_client(monkeypatch, httpx.MockTransport(primary_handler), httpx.MockTransport(fallback_handler))
    try:
        chunks = [chunk async for chunk in client.chat_stream(messages=[{"role": "user", "content": "hi"}])]
    finally:
        await client.close()

    assert chunks == ["fallback stream"]
