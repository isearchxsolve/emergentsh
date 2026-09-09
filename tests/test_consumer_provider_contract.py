from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core import providers


PROFILE_WITH_UPSTREAM_METADATA = {
    "name": "legacy-profile",
    "key": "must-not-be-forwarded",
    "default_model": "glm",
    "models": {"glm": {"id": "z-ai/glm-5.2"}},
    "rpm": 17.0,
}


class RecordingOpenAI:
    instances: list[SimpleNamespace] = []

    def __init__(self, *, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: []))
        self.__class__.instances.append(self)


def test_pool_uses_one_canonical_route_and_never_profile_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMNIROUTE_BASE_URL", providers.CANONICAL_CONSUMER_BASE_URL)
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    RecordingOpenAI.instances.clear()
    monkeypatch.setattr(providers, "OpenAI", RecordingOpenAI)

    pool = providers.build_provider_pool(PROFILE_WITH_UPSTREAM_METADATA)

    assert len(pool.providers) == 1
    route = pool.providers[0]
    assert route.name == "OmniRoute"
    assert route.model_id == providers.CANONICAL_CONSUMER_MODEL
    assert route.bucket.rpm == 17.0 * 0.8
    assert len(RecordingOpenAI.instances) == 1
    assert RecordingOpenAI.instances[0].base_url == providers.CANONICAL_CONSUMER_BASE_URL
    assert RecordingOpenAI.instances[0].api_key == ""


def test_desktop_base_override_is_rejected_before_openai_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
    with pytest.raises(ValueError, match="canonical consumer endpoint"):
        providers.configured_consumer_base_url()
    with pytest.raises(ValueError, match="canonical consumer endpoint"):
        providers.build_provider_pool(PROFILE_WITH_UPSTREAM_METADATA)


def test_provider_constructor_rejects_upstream_url_or_model() -> None:
    with pytest.raises(ValueError, match="canonical consumer endpoint"):
        providers.Provider(
            "legacy",
            "https://upstream.invalid/v1",
            "ignored",
            providers.CANONICAL_CONSUMER_MODEL,
            20.0,
        )


def test_agent_core_wire_payload_is_pinned_to_consumer_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """Role/profile model labels must never leak into the OpenAI request body."""
    monkeypatch.setenv("OMNIROUTE_BASE_URL", providers.CANONICAL_CONSUMER_BASE_URL)
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    calls: list[dict] = []

    class Completions:
        def create(self, **payload):
            calls.append(payload)
            choice = SimpleNamespace(
                finish_reason="stop",
                delta=SimpleNamespace(content="done", reasoning_content=None, tool_calls=[]),
            )
            return [SimpleNamespace(choices=[choice])]

    class AgentOpenAI:
        def __init__(self, *, base_url: str, api_key: str, timeout: float) -> None:
            self.base_url = base_url
            self.api_key = api_key
            self.timeout = timeout
            self.chat = SimpleNamespace(completions=Completions())

    monkeypatch.setattr(providers, "OpenAI", AgentOpenAI)
    monkeypatch.setattr("src.core.config.ConfigManager.save_session", lambda *args, **kwargs: None)

    from src.core.agent_core import NIMAgentCore
    from src.core.signals import AgentSignals

    agent = NIMAgentCore(PROFILE_WITH_UPSTREAM_METADATA, ".", AgentSignals())
    agent.run("say hello")

    assert calls
    assert calls[0]["model"] == providers.CANONICAL_CONSUMER_MODEL
    assert "extra_body" not in calls[0]
    assert agent.pool.providers[0].client.base_url == providers.CANONICAL_CONSUMER_BASE_URL
    assert agent.pool.providers[0].client.api_key == ""
    with pytest.raises(ValueError, match="canonical consumer model"):
        providers.Provider(
            "legacy",
            providers.CANONICAL_CONSUMER_BASE_URL,
            "ignored",
            "z-ai/glm-5.2",
            20.0,
        )
