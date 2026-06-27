import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import MagicMock
from jurbas_code.agent import Agent
from jurbas_code.commands import handle_command, cmd_help, cmd_status, cmd_clear, cmd_version

@pytest.fixture
def mock_agent():
    client = MagicMock()
    client.models.list.return_value.data = [MagicMock(id="test-model")]

    agent = Agent(client=client, provider="deepseek")
    agent.session_tokens = {"prompt": 10, "completion": 20, "total": 30}
    agent.messages = [{"role": "system", "content": "System prompt"}, {"role": "user", "content": "Hello"}]
    return agent

def test_cmd_help(mock_agent):
    result = handle_command(mock_agent, "/help")
    assert "Available commands:" in result
    assert "/help" in result
    assert "/status" in result
    assert "/clear" in result
    assert "/version" in result

def test_cmd_status(mock_agent):
    result = handle_command(mock_agent, "/status")
    assert "Session Status:" in result
    assert "Provider: deepseek" in result
    assert "Tokens: 10 prompt / 20 completion / 30 total" in result

def test_cmd_clear(mock_agent):
    result = handle_command(mock_agent, "/clear")
    assert result == "Conversation history cleared."
    assert len(mock_agent.messages) == 1
    assert mock_agent.messages[0]["role"] == "system"
    assert mock_agent.messages[0]["content"] == "System prompt"

def test_cmd_clear_empty(mock_agent):
    mock_agent.messages = []
    result = handle_command(mock_agent, "/clear")
    assert result == "History already clear."
    assert len(mock_agent.messages) == 0

def test_cmd_version(mock_agent):
    from jurbas_code import __version__
    result = handle_command(mock_agent, "/version")
    assert f"Jurbas-Code version: {__version__}" in result

def test_unknown_command(mock_agent):
    result = handle_command(mock_agent, "/nonexistent")
    assert result == "Unknown command: /nonexistent"

def test_agent_intercepts_command(mock_agent):
    on_ai_reply = MagicMock()

    # Send command
    mock_agent.chat("/version", on_ai_reply=on_ai_reply)

    # Should reply immediately and not add to messages or call the model
    from jurbas_code import __version__
    on_ai_reply.assert_called_once_with(f"Jurbas-Code version: {__version__}")

    # Message list length shouldn't change
    assert len(mock_agent.messages) == 2
    assert mock_agent.messages[-1]["content"] != "/version"

    # Model shouldn't be called
    mock_agent.client.chat.completions.create.assert_not_called()
