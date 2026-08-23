"""Tests for NIM API client - RED phase."""
import pytest
from unittest.mock import patch, MagicMock
from backend.nim_client import NIMClient, NIMConfig


def test_nim_config_defaults():
    config = NIMConfig(api_key="test-key")
    assert config.api_key == "test-key"
    assert config.base_url == "https://api.nv.nvidia.com/v1"
    assert config.default_model == "nvidia/llama-3.1-nim-70b"
    assert config.timeout == 30
    assert config.max_tokens == 4096
    assert config.temperature == 0.7


def test_nim_client_init():
    client = NIMClient(api_key="test-key", base_url="https://api.nv.nvidia.com/v1")
    assert client.api_key == "test-key"
    assert client.base_url == "https://api.nv.nvidia.com/v1"


def test_chat_completion_returns_response():
    client = NIMClient(api_key="test-key", base_url="https://api.nv.nvidia.com/v1")
    mock_response = {
        "id": "chatcmpl-123",
        "choices": [{"message": {"role": "assistant", "content": "Hello!"}}],
    }
    with patch.object(client, "_post", return_value=mock_response):
        result = client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}]
        )
    assert result["choices"][0]["message"]["content"] == "Hello!"


def test_chat_completion_with_model():
    client = NIMClient(api_key="test-key", base_url="https://api.nv.nvidia.com/v1")
    mock_response = {"choices": [{"message": {"content": "OK"}}]}
    with patch.object(client, "_post", return_value=mock_response) as mock_post:
        client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="nvidia/llama-3.1-nim-405b",
        )
    call_args = mock_post.call_args
    assert call_args[0][0] == "/chat/completions"
    body = call_args[0][1]
    assert body["model"] == "nvidia/llama-3.1-nim-405b"


def test_get_models_returns_list():
    client = NIMClient(api_key="test-key", base_url="https://api.nv.nvidia.com/v1")
    mock_response = {"data": [{"id": "model-1"}, {"id": "model-2"}]}
    with patch.object(client, "_get", return_value=mock_response):
        models = client.get_models()
    assert models == ["model-1", "model-2"]


def test_chat_completion_missing_api_key_raises():
    with pytest.raises(ValueError):
        NIMClient(api_key="", base_url="https://api.nv.nvidia.com/v1")
