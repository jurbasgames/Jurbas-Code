import os
import pytest
from unittest import mock
from jurbas_code import providers
from jurbas_code.agent import Agent

def test_get_client_codex_with_codex_key():
    with mock.patch.dict(os.environ, {"CODEX_API_KEY": "codex-key"}, clear=True):
        with mock.patch("openai.OpenAI") as mock_openai:
            client = providers.get_client("codex")
            mock_openai.assert_called_once_with(api_key="codex-key")
            assert client == mock_openai.return_value

def test_get_client_codex_with_openai_key_fallback():
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key"}, clear=True):
        if "CODEX_API_KEY" in os.environ:
            del os.environ["CODEX_API_KEY"]
        with mock.patch("openai.OpenAI") as mock_openai:
            client = providers.get_client("codex")
            mock_openai.assert_called_once_with(api_key="openai-key")
            assert client == mock_openai.return_value

def test_resolve_codex_model_default():
    with mock.patch.dict(os.environ, {}, clear=True):
        client = mock.Mock()
        client.models.list.return_value = []
        model = providers.resolve_provider_model("codex", client)
        assert model == "gpt-4o"

def test_resolve_codex_model_env():
    with mock.patch.dict(os.environ, {"CODEX_MODEL": "gpt-codex-v1"}, clear=True):
        client = mock.Mock()
        model = providers.resolve_provider_model("codex", client)
        assert model == "gpt-codex-v1"

def test_agent_chat_codex_no_reasoning_effort():
    mock_client = mock.Mock()
    # Setup mock for streaming response
    mock_chunk = mock.Mock()
    mock_chunk.choices = [mock.Mock(delta=mock.Mock(content="Hello", role="assistant", tool_calls=None))]
    mock_client.chat.completions.create.return_value = [mock_chunk]

    agent = Agent(mock_client, "codex")
    with mock.patch("jurbas_code.agent.resolve_provider_model", return_value="gpt-4o"):
        agent.chat("Hi")

    # Verify that reasoning_effort and extra_body are NOT passed for codex
    args, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o"
    assert "reasoning_effort" not in kwargs
    assert "extra_body" not in kwargs
    assert kwargs["stream"] is True

def test_agent_chat_codex_authentication_error():
    mock_client = mock.Mock()
    from openai import AuthenticationError
    mock_client.chat.completions.create.side_effect = AuthenticationError(
        "Invalid key",
        response=mock.Mock(status_code=401),
        body={}
    )

    agent = Agent(mock_client, "codex")
    with mock.patch.dict(os.environ, {"CODEX_API_KEY": "sk-codex-123456"}):
        with mock.patch("jurbas_code.agent.resolve_provider_model", return_value="gpt-4o"):
            with mock.patch("sys.exit") as mock_exit:
                agent.chat("Hi")
                mock_exit.assert_called_once_with(1)
