from __future__ import annotations

import json

import httpx
import pytest

from backend.app.services.nim_client import AsyncNIMClient


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
