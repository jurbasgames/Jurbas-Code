import pytest
from unittest.mock import MagicMock, patch
from jurbas_code.agent import Agent

@pytest.fixture
def mock_client():
    client = MagicMock()
    # Mocking _listed_model_ids is easier via patch, but we can also set the structure for openai mock
    models_mock = MagicMock()
    model_item_1 = MagicMock()
    model_item_1.id = "model-a"
    model_item_2 = MagicMock()
    model_item_2.id = "model-b"
    models_mock.list.return_value.data = [model_item_1, model_item_2]
    client.models = models_mock
    return client

@patch("jurbas_code.agent._listed_model_ids")
@patch("jurbas_code.agent.resolve_provider_model")
def test_model_no_args_shows_available(mock_resolve, mock_listed, mock_client):
    mock_resolve.return_value = "default-model"
    mock_listed.return_value = ["model-a", "model-b"]

    agent = Agent(mock_client, "deepseek")

    replies = []
    agent.chat("/model", on_ai_reply=lambda r: replies.append(r))

    assert len(replies) == 1
    assert "Current model: default-model" in replies[0]
    assert "Available models for 'deepseek': model-a, model-b" in replies[0]
    assert agent.session_model is None

    # Check that no messages were added to context for a slash command
    assert len(agent.messages) == 1 # Just system prompt

@patch("jurbas_code.agent.get_client")
@patch("jurbas_code.agent._listed_model_ids")
def test_model_provider_arg_lists_provider_models(mock_listed, mock_get_client, mock_client):
    temp_client = MagicMock()
    mock_get_client.return_value = temp_client
    mock_listed.return_value = ["claude-1", "claude-2"]

    agent = Agent(mock_client, "deepseek")

    replies = []
    agent.chat("/model claude", on_ai_reply=lambda r: replies.append(r))

    assert len(replies) == 1
    assert "Available models for 'claude': claude-1, claude-2" in replies[0]
    mock_get_client.assert_called_once_with("claude")
    assert agent.session_model is None

def test_model_switch_model(mock_client):
    agent = Agent(mock_client, "deepseek")

    replies = []
    agent.chat("/model deepseek-v4-pro", on_ai_reply=lambda r: replies.append(r))

    assert len(replies) == 1
    assert "Session model switched to: deepseek-v4-pro" in replies[0]
    assert agent.session_model == "deepseek-v4-pro"

@patch("jurbas_code.agent._listed_model_ids")
@patch("jurbas_code.agent.resolve_provider_model")
def test_model_api_failure_fallback(mock_resolve, mock_listed, mock_client):
    mock_resolve.return_value = "default-model"
    mock_listed.side_effect = Exception("API down")

    agent = Agent(mock_client, "deepseek")

    replies = []
    agent.chat("/model", on_ai_reply=lambda r: replies.append(r))

    assert len(replies) == 1
    assert "Unknown (API unavailable)" in replies[0]
