import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main

def test_normalize_tool_call_accepts_function_dict():
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function={"name": "read_file", "arguments": '{"file_path": "test.txt"}'},
    )

    assert main.normalize_tool_call(tool_call) == {
        "id": "call_123",
        "type": "function",
        "function": {"name": "read_file", "arguments": '{"file_path": "test.txt"}'},
    }

# === TESTS FOR main() ===
@patch('openai.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
def test_main_loop_exit(mock_print, mock_input, mock_openai):
    # Setup to exit immediately
    mock_input.return_value = "exit"

    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek"}):
        main.main()

    mock_openai.assert_called_once()
    mock_print.assert_not_called()

@patch('openai.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
@patch('jurbas_code.tools.read_file')
def test_main_loop_with_tool_call(mock_read_file, mock_print, mock_input, mock_openai):
    # Input first iteration "do something", second iteration "quit"
    mock_input.side_effect = ["read something", "quit"]

    # Setup OpenAI client mock
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # First response: tool call
    mock_response_1 = MagicMock()
    mock_response_1.usage.prompt_tokens = None
    mock_response_1.usage.completion_tokens = None
    mock_response_1.usage.total_tokens = None
    mock_response_1.choices[0].finish_reason = "tool_calls"
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = '{"file_path": "test.txt"}'
    mock_tool_call.id = "call_123"
    mock_response_1.choices[0].message.tool_calls = [mock_tool_call]
    mock_response_1.choices[0].message.model_dump.return_value = {"role": "assistant", "tool_calls": [{"id": "call_123"}]}

    # Second response (after tool result): final text
    mock_response_2 = MagicMock()
    mock_response_2.usage.prompt_tokens = 20
    mock_response_2.usage.completion_tokens = 10
    mock_response_2.usage.total_tokens = 30
    mock_response_2.choices[0].finish_reason = "stop"
    mock_response_2.choices[0].message.content = "Here is the content"
    mock_response_2.choices[0].message.model_dump.return_value = {"role": "assistant", "content": "Here is the content"}

    mock_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

    # Setup tool mock
    mock_read_file.return_value = "mocked file content"

    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek"}):
        main.main()

    # Check if tool was actually called
    mock_read_file.assert_called_once_with("test.txt")

    # Check if AI's final text was printed
    mock_print.assert_any_call("AI: Here is the content\n")

    # Check token metrics printing
    mock_print.assert_any_call("  [Tokens] Request: 0p / 0c (0 total) | Session: 0p / 0c (0 total)")
    mock_print.assert_any_call("  [Tokens] Request: 20p / 10c (30 total) | Session: 20p / 10c (30 total)")
