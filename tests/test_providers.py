import os
import pytest
from types import SimpleNamespace
from unittest import mock
from jurbas_code import providers


def test_get_client_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider: unknown"):
        providers.get_client("unknown")


def test_get_claude_client_no_credentials():
    # Mock resolve_claude_token to return None
    with mock.patch("jurbas_code.providers.resolve_claude_token", return_value=None):
        with mock.patch.dict(os.environ, {}, clear=True):
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]
            with pytest.raises(
                RuntimeError, match="Nao encontrei credenciais do Claude Code"
            ):
                providers.get_claude_client()


def test_get_claude_client_anthropic_api_key_guard():
    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-xxx"}):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY esta setado"):
            providers.get_claude_client()


def test_get_claude_client_uses_oauth_auth_token_not_api_key():
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch(
            "jurbas_code.providers.resolve_claude_token", return_value="oauth-token"
        ):
            with mock.patch("anthropic.Anthropic") as mock_anthropic:
                providers.get_claude_client()

    mock_anthropic.assert_called_once()
    _, kwargs = mock_anthropic.call_args
    assert kwargs["auth_token"] == "oauth-token"
    assert "api_key" not in kwargs
    assert kwargs["default_headers"]["x-app"] == "cli"


def test_convert_to_anthropic_tools():
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    anthropic_tools = providers.convert_to_anthropic_tools(openai_tools)
    assert len(anthropic_tools) == 1
    assert anthropic_tools[0]["name"] == "test_tool"
    assert anthropic_tools[0]["description"] == "A test tool"
    assert "input_schema" in anthropic_tools[0]


def test_convert_to_anthropic_tools_handles_missing_optional_fields():
    anthropic_tools = providers.convert_to_anthropic_tools(
        [{"type": "function", "function": {"name": "minimal_tool"}}]
    )

    assert anthropic_tools == [
        {
            "name": "minimal_tool",
            "description": "",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]


def test_convert_messages_to_anthropic():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": "hi",
            "tool_calls": [
                {"id": "1", "function": {"name": "tool", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "1", "content": "result"},
    ]
    anthropic_msgs = providers.convert_messages_to_anthropic(messages)
    # System message is skipped
    assert len(anthropic_msgs) == 3
    assert anthropic_msgs[0]["role"] == "user"
    assert anthropic_msgs[1]["role"] == "assistant"
    assert anthropic_msgs[2]["role"] == "user"  # tool result wrapped in user message


def test_convert_messages_merges_tool_result_into_existing_user_message():
    messages = [
        {"role": "user", "content": "run tool"},
        {"role": "tool", "tool_call_id": "call_1", "content": "tool output"},
    ]

    anthropic_msgs = providers.convert_messages_to_anthropic(messages)

    assert [m["role"] for m in anthropic_msgs] == ["user"]
    assert anthropic_msgs[0]["content"] == [
        {"type": "text", "text": "run tool"},
        {"type": "tool_result", "tool_use_id": "call_1", "content": "tool output"},
    ]


def test_convert_messages_accepts_dict_and_invalid_tool_arguments():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "dict_args",
                    "function": {"name": "tool", "arguments": {"a": 1}},
                },
                {
                    "id": "bad_args",
                    "function": {"name": "tool", "arguments": "{bad json"},
                },
            ],
        },
    ]

    anthropic_msgs = providers.convert_messages_to_anthropic(messages)

    assert anthropic_msgs[0]["content"][0]["input"] == {"a": 1}
    assert anthropic_msgs[0]["content"][1]["input"] == {}


def test_normalize_tool_call_accepts_function_dict():
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function={"name": "read_file", "arguments": '{"file_path": "test.txt"}'},
    )

    assert providers.normalize_tool_call(tool_call) == {
        "id": "call_123",
        "type": "function",
        "function": {"name": "read_file", "arguments": '{"file_path": "test.txt"}'},
    }
