import os
import pytest
from unittest import mock
from jurbas_code import providers

def test_get_client_unknown_provider():
    with pytest.raises(ValueError, match="Provider desconhecido: unknown"):
        providers.get_client("unknown")

def test_get_claude_client_no_credentials():
    # Mock resolve_claude_token to return None
    with mock.patch("jurbas_code.providers.resolve_claude_token", return_value=None):
        with mock.patch.dict(os.environ, {}, clear=True):
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]
            with pytest.raises(RuntimeError, match="Nao encontrei credenciais do Claude Code"):
                providers.get_claude_client()

def test_get_claude_client_anthropic_api_key_guard():
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-xxx"}):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY esta setado"):
            providers.get_claude_client()

def test_convert_to_anthropic_tools():
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]
    anthropic_tools = providers.convert_to_anthropic_tools(openai_tools)
    assert len(anthropic_tools) == 1
    assert anthropic_tools[0]["name"] == "test_tool"
    assert anthropic_tools[0]["description"] == "A test tool"
    assert "input_schema" in anthropic_tools[0]

def test_convert_messages_to_anthropic():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi", "tool_calls": [
            {"id": "1", "function": {"name": "tool", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "1", "content": "result"}
    ]
    anthropic_msgs = providers.convert_messages_to_anthropic(messages)
    # System message is skipped
    assert len(anthropic_msgs) == 3
    assert anthropic_msgs[0]["role"] == "user"
    assert anthropic_msgs[1]["role"] == "assistant"
    assert anthropic_msgs[2]["role"] == "user" # tool result wrapped in user message
