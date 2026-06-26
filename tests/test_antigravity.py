import os
import pytest
from unittest.mock import MagicMock, patch
from jurbas_code.providers.antigravity import AntigravityProvider
from jurbas_code.providers import get_client
from openai import AuthenticationError

def test_antigravity_provider_missing_key():
    with patch.dict(os.environ, {}, clear=True):
        if "ANTIGRAVITY_API_KEY" in os.environ:
            del os.environ["ANTIGRAVITY_API_KEY"]
        provider = AntigravityProvider()
        with pytest.raises(RuntimeError, match="ANTIGRAVITY_API_KEY environment variable is not set"):
            provider.get_client()

def test_antigravity_provider_with_key():
    with patch.dict(os.environ, {"ANTIGRAVITY_API_KEY": "test-key"}):
        provider = AntigravityProvider()
        with patch("jurbas_code.providers.antigravity.OpenAI") as mock_openai:
            client = provider.get_client()
            mock_openai.assert_called_once_with(
                api_key="test-key",
                base_url="https://api.antigravity.ai"
            )

def test_get_client_antigravity():
    with patch.dict(os.environ, {"ANTIGRAVITY_API_KEY": "test-key"}):
        with patch("jurbas_code.providers.antigravity.OpenAI") as mock_openai:
            client = get_client("antigravity")
            mock_openai.assert_called_once_with(
                api_key="test-key",
                base_url="https://api.antigravity.ai"
            )

def test_antigravity_provider_custom_url():
    with patch.dict(os.environ, {
        "ANTIGRAVITY_API_KEY": "test-key",
        "ANTIGRAVITY_BASE_URL": "https://custom.antigravity.ai"
    }):
        provider = AntigravityProvider()
        with patch("jurbas_code.providers.antigravity.OpenAI") as mock_openai:
            client = provider.get_client()
            mock_openai.assert_called_once_with(
                api_key="test-key",
                base_url="https://custom.antigravity.ai"
            )

@patch("jurbas_code.providers.resolve_provider_model")
def test_agent_with_antigravity(mock_resolve_model):
    from jurbas_code.agent import Agent
    mock_resolve_model.return_value = "antigravity-default"
    mock_client = MagicMock()

    # Mock chat.completions.create response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].message.content = "Antigravity response"
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.model_dump.return_value = {"role": "assistant", "content": "Antigravity response"}
    mock_response.usage.prompt_tokens = 5
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 10

    mock_client.chat.completions.create.return_value = mock_response

    agent = Agent(mock_client, provider="antigravity")
    on_ai_reply = MagicMock()
    agent.chat("Hello Antigravity", on_ai_reply=on_ai_reply)

    on_ai_reply.assert_called_once_with("Antigravity response")
    assert agent.messages[-1]["content"] == "Antigravity response"
