import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import json
from unittest.mock import MagicMock, patch
from jurbas_code.agent import Agent

@pytest.fixture
def mock_client():
    return MagicMock()

def test_agent_final_assistant_reply(mock_client):
    agent = Agent(mock_client, provider="deepseek")

    mock_response = MagicMock()
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].message.content = "Hello there!"
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.model_dump.return_value = {"role": "assistant", "content": "Hello there!"}
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15

    mock_client.chat.completions.create.return_value = mock_response

    on_ai_reply = MagicMock()
    agent.chat("Hi", on_ai_reply=on_ai_reply)

    on_ai_reply.assert_called_once_with("Hello there!")
    assert agent.messages[-1] == {"role": "assistant", "content": "Hello there!"}
    assert agent.session_tokens["total"] == 15

def test_agent_tool_call_roundtrip(mock_client):
    agent = Agent(mock_client, provider="deepseek")

    # First response: tool call
    mock_response_1 = MagicMock()
    mock_response_1.choices[0].finish_reason = "tool_calls"
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = '{"file_path": "test.txt"}'
    mock_response_1.choices[0].message.tool_calls = [mock_tool_call]
    mock_response_1.choices[0].message.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "test.txt"}'}
        }]
    }
    mock_response_1.usage.prompt_tokens = 10
    mock_response_1.usage.completion_tokens = 10
    mock_response_1.usage.total_tokens = 20

    # Second response: final stop
    mock_response_2 = MagicMock()
    mock_response_2.choices[0].finish_reason = "stop"
    mock_response_2.choices[0].message.content = "I read it."
    mock_response_2.choices[0].message.tool_calls = None
    mock_response_2.choices[0].message.model_dump.return_value = {"role": "assistant", "content": "I read it."}
    mock_response_2.usage.prompt_tokens = 30
    mock_response_2.usage.completion_tokens = 5
    mock_response_2.usage.total_tokens = 35

    mock_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

    with patch("jurbas_code.agent.read_file", return_value="file content"):
        on_tool_result = MagicMock()
        agent.chat("Read test.txt", on_tool_result=on_tool_result)

    on_tool_result.assert_called_once_with("read_file", "file content")
    assert any(m["role"] == "tool" and m["content"] == "file content" for m in agent.messages)
    assert agent.messages[-1]["content"] == "I read it."
    assert agent.session_tokens["total"] == 55

def test_agent_max_tool_steps(mock_client):
    # Set max_tool_steps to 1 for easy testing
    agent = Agent(mock_client, provider="deepseek", max_tool_steps=1)

    mock_response = MagicMock()
    mock_response.choices[0].finish_reason = "tool_calls"
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = '{"file_path": "test.txt"}'
    mock_response.choices[0].message.tool_calls = [mock_tool_call]
    mock_response.choices[0].message.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "test.txt"}'}
        }]
    }
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20

    mock_client.chat.completions.create.return_value = mock_response

    on_ai_reply = MagicMock()
    with patch("jurbas_code.agent.read_file", return_value="content"):
        agent.chat("Keep reading", on_ai_reply=on_ai_reply)

    on_ai_reply.assert_called_once_with("stopped after reaching the max of 1 tool steps.")

def test_agent_invalid_tool_arguments(mock_client):
    agent = Agent(mock_client, provider="deepseek")

    mock_response_1 = MagicMock()
    mock_response_1.choices[0].finish_reason = "tool_calls"
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "read_file"
    # Invalid JSON
    mock_tool_call.function.arguments = '{"file_path": "test.txt"'
    mock_response_1.choices[0].message.tool_calls = [mock_tool_call]
    mock_response_1.choices[0].message.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"file_path": "test.txt"' }
        }]
    }
    mock_response_1.usage.prompt_tokens = 10
    mock_response_1.usage.completion_tokens = 10
    mock_response_1.usage.total_tokens = 20

    mock_response_2 = MagicMock()
    mock_response_2.choices[0].finish_reason = "stop"
    mock_response_2.choices[0].message.content = "Fixed it."
    mock_response_2.choices[0].message.tool_calls = None
    mock_response_2.choices[0].message.model_dump.return_value = {"role": "assistant", "content": "Fixed it."}
    mock_response_2.usage.prompt_tokens = 20
    mock_response_2.usage.completion_tokens = 5
    mock_response_2.usage.total_tokens = 25

    mock_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

    on_tool_call = MagicMock()
    agent.chat("Read it", on_tool_call=on_tool_call)

    # Verify tool call callback was called with error
    args, kwargs = on_tool_call.call_args
    assert args[0] == "read_file"
    assert "error" in kwargs

    # Verify tool result message contains error
    tool_msg = next(m for m in agent.messages if m["role"] == "tool")
    assert "Error: invalid JSON arguments" in tool_msg["content"]


def test_agent_claude_authentication_error(mock_client, capsys):
    agent = Agent(mock_client, provider="claude")
    import anthropic
    import httpx
    mock_response = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com"))
    mock_client.messages.create.side_effect = anthropic.AuthenticationError(
        message="Auth error",
        response=mock_response,
        body=None
    )
    with pytest.raises(SystemExit):
        agent.chat("Hi")
    captured = capsys.readouterr()
    assert "AI: Authentication Error:" in captured.out


def test_agent_claude_uses_current_default_model(mock_client):
    agent = Agent(mock_client, provider="claude")
    text_block = MagicMock(type="text", text="pong")
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 1
    mock_response.usage.output_tokens = 1
    mock_response.content = [text_block]
    mock_client.messages.create.return_value = mock_response

    on_ai_reply = MagicMock()
    with patch.dict(os.environ, {}, clear=True):
        agent.chat("ping", on_ai_reply=on_ai_reply)

    kwargs = mock_client.messages.create.call_args.kwargs
    legacy_model = "claude-3-7" "-sonnet-20250219"
    assert kwargs["model"] == "claude-sonnet-4-6"
    assert kwargs["model"] != legacy_model
    on_ai_reply.assert_called_once_with("pong")


def test_agent_claude_model_can_be_overridden_with_env(mock_client):
    agent = Agent(mock_client, provider="claude")
    text_block = MagicMock(type="text", text="pong")
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 1
    mock_response.usage.output_tokens = 1
    mock_response.content = [text_block]
    mock_client.messages.create.return_value = mock_response

    with patch.dict(os.environ, {"CLAUDE_MODEL": "claude-test-model"}, clear=True):
        agent.chat("ping")

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-test-model"


def test_agent_claude_rate_limit_error(mock_client, capsys):
    agent = Agent(mock_client, provider="claude")
    import anthropic
    import httpx
    mock_response = httpx.Response(429, request=httpx.Request("POST", "https://api.anthropic.com"))
    mock_client.messages.create.side_effect = anthropic.RateLimitError(
        message="Rate limit",
        response=mock_response,
        body=None
    )
    agent.chat("Hi")
    captured = capsys.readouterr()
    assert "AI: Rate Limit Error:" in captured.out


def test_agent_claude_timeout_error(mock_client, capsys):
    agent = Agent(mock_client, provider="claude")
    import anthropic
    import httpx
    mock_request = httpx.Request("POST", "https://api.anthropic.com")
    mock_client.messages.create.side_effect = anthropic.APITimeoutError(
        request=mock_request
    )
    agent.chat("Hi")
    captured = capsys.readouterr()
    assert "AI: Timeout Error:" in captured.out


def test_agent_claude_api_error(mock_client, capsys):
    agent = Agent(mock_client, provider="claude")
    agent.messages = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}, {"role": "user", "content": "How are you?"}]
    import anthropic
    import httpx
    mock_request = httpx.Request("POST", "https://api.anthropic.com")
    mock_client.messages.create.side_effect = anthropic.APIError(
        message="API error",
        request=mock_request,
        body=None
    )
    agent.chat("How are you?")
    captured = capsys.readouterr()
    assert "AI: API Error:" in captured.out
    assert len(agent.messages) == 3
    assert agent.messages[-1] == {"role": "user", "content": "How are you?"}


def test_agent_claude_unexpected_error(mock_client, capsys):
    agent = Agent(mock_client, provider="claude")
    mock_client.messages.create.side_effect = Exception("Unexpected")
    agent.chat("Hi")
    captured = capsys.readouterr()
    assert "AI: Unexpected Error:" in captured.out

