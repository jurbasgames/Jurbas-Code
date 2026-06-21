import pytest
from unittest.mock import patch, MagicMock
import os
import sys
import shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main

# === TESTS FOR safe_path() ===
def test_safe_path_allowed():
    # Test path resolution inside ALLOWED_BASE
    # mock abspath returning an allowed path
    with patch('os.path.abspath', return_value=os.path.abspath(main.ALLOWED_BASE + "/test.txt")):
         assert main.safe_path("test.txt") == os.path.abspath(main.ALLOWED_BASE + "/test.txt")

def test_safe_path_denied():
    # Test path resolution outside ALLOWED_BASE
    with patch('os.path.abspath', return_value="/tmp/test.txt"):
        with pytest.raises(PermissionError) as exc_info:
            main.safe_path("../../../tmp/test.txt")
        assert "Path not allowed" in str(exc_info.value)

# === TESTS FOR read_file() ===
@patch('main.safe_path')
@patch('os.path.exists')
@patch('builtins.open', new_callable=MagicMock)
def test_read_file_success(mock_open, mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = True

    # Mocking open().read()
    mock_file = MagicMock()
    mock_file.read.return_value = "file content"
    mock_open.return_value.__enter__.return_value = mock_file

    assert main.read_file("test.txt") == "file content"
    mock_open.assert_called_once_with("/allowed/test.txt", "r", encoding="utf-8")

@patch('main.safe_path')
def test_read_file_permission_error(mock_safe_path):
    mock_safe_path.side_effect = PermissionError("Path not allowed: test.txt")
    assert "Error: Path not allowed: test.txt" in main.read_file("test.txt")

@patch('main.safe_path')
@patch('os.path.exists')
def test_read_file_not_found(mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = False
    assert "Error: file 'test.txt' not found." in main.read_file("test.txt")

# === TESTS FOR list_directory() ===
@patch('main.safe_path')
@patch('os.path.exists')
@patch('os.path.isdir')
@patch('os.listdir')
@patch('os.path.getsize')
def test_list_directory_success(mock_getsize, mock_listdir, mock_isdir, mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/dir"
    mock_exists.return_value = True

    # Let os.path.isdir return True for the directory itself, and decide for items
    def isdir_side_effect(path):
        if path == "/allowed/dir": return True
        if path.endswith("subdir"): return True
        return False
    mock_isdir.side_effect = isdir_side_effect

    mock_listdir.return_value = ["file1.txt", "subdir"]
    mock_getsize.return_value = 1024 # 1.0 KB

    result = main.list_directory("dir")

    assert "Contents of 'dir' (2 items):" in result
    assert "[FILE] file1.txt (1.0 KB)" in result
    assert "[DIR] subdir" in result

@patch('main.safe_path')
def test_list_directory_permission_error(mock_safe_path):
    mock_safe_path.side_effect = PermissionError("Path not allowed")
    assert "Error: Path not allowed" in main.list_directory("dir")

@patch('main.safe_path')
@patch('os.path.exists')
def test_list_directory_not_found(mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/dir"
    mock_exists.return_value = False
    assert "Error: directory 'dir' not found." in main.list_directory("dir")

@patch('main.safe_path')
@patch('os.path.exists')
@patch('os.path.isdir')
def test_list_directory_not_a_dir(mock_isdir, mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/file.txt"
    mock_exists.return_value = True
    mock_isdir.return_value = False
    assert "Error: 'file.txt' is not a directory." in main.list_directory("file.txt")

# === TESTS FOR write_file() ===
@patch('main.safe_path')
@patch('os.makedirs')
@patch('os.path.exists')
@patch('shutil.copy2')
@patch('os.path.getsize')
@patch('builtins.open', new_callable=MagicMock)
def test_write_file_success(mock_open, mock_getsize, mock_copy2, mock_exists, mock_makedirs, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = False # No backup needed
    mock_getsize.return_value = 12

    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file

    result = main.write_file("test.txt", "file content")

    mock_makedirs.assert_called_once_with("/allowed", exist_ok=True)
    mock_open.assert_called_once_with("/allowed/test.txt", "w", encoding="utf-8")
    mock_file.write.assert_called_once_with("file content")
    mock_copy2.assert_not_called()
    assert "written successfully (12 bytes)" in result

@patch('main.safe_path')
@patch('os.makedirs')
@patch('os.path.exists')
@patch('shutil.copy2')
@patch('os.path.getsize')
@patch('builtins.open', new_callable=MagicMock)
def test_write_file_with_backup(mock_open, mock_getsize, mock_copy2, mock_exists, mock_makedirs, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = True # Needs backup
    mock_getsize.return_value = 12

    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file

    result = main.write_file("test.txt", "file content")

    mock_copy2.assert_called_once_with("/allowed/test.txt", "/allowed/test.txt.bak")
    assert "previous version backed up to 'test.txt.bak'" in result

@patch('main.safe_path')
def test_write_file_permission_error(mock_safe_path):
    mock_safe_path.side_effect = PermissionError("Path not allowed")
    assert "Error: Path not allowed" in main.write_file("test.txt", "content")

# === TESTS FOR main() ===
@patch('main.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
def test_main_loop_exit(mock_print, mock_input, mock_openai):
    # Setup to exit immediately
    with patch('os.environ.get', return_value="sk-test-key"):
        mock_input.return_value = "exit"
        main.main()
        mock_openai.assert_called_once()
        mock_print.assert_not_called()

@patch('main.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
@patch('main.read_file')
def test_main_loop_with_tool_call(mock_read_file, mock_print, mock_input, mock_openai):
    # Input first iteration "do something", second iteration "quit"
    with patch('os.environ.get', return_value="sk-test-key"):
        mock_input.side_effect = ["read something", "quit"]

        # Setup OpenAI client mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # First response: tool call
        mock_response_1 = MagicMock()
        mock_response_1.choices[0].finish_reason = "tool_calls"
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = '{"file_path": "test.txt"}'
        mock_tool_call.id = "call_123"
        mock_response_1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response_1.choices[0].message.model_dump.return_value = {"role": "assistant", "tool_calls": [{"id": "call_123"}]}
        mock_response_1.usage = None

        # Second response (after tool result): final text
        mock_response_2 = MagicMock()
        mock_response_2.choices[0].finish_reason = "stop"
        mock_response_2.choices[0].message.content = "Here is the content"
        mock_response_2.choices[0].message.model_dump.return_value = {"role": "assistant", "content": "Here is the content"}
        mock_response_2.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)

        mock_client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

        # Setup tool mock
        mock_read_file.return_value = "mocked file content"

        main.main()

        # Check if tool was actually called
        mock_read_file.assert_called_once_with("test.txt")

        # Check if AI's final text was printed
        mock_print.assert_any_call("AI: Here is the content\n")

        # Check token metrics printing
        mock_print.assert_any_call("  [Tokens] Request: 20p / 10c (30 total) | Session: 20p / 10c (30 total)")

def test_main_missing_api_key():
    with patch('os.environ.get', return_value=None):
        with patch('sys.exit', side_effect=SystemExit) as mock_exit:
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit):
                    main.main()
                mock_print.assert_any_call("Error: DEEPSEEK_API_KEY environment variable is not set or is empty.")
                mock_exit.assert_called_once_with(1)

def test_main_authentication_error_exits():
    # Mocking first interaction results in AuthenticationError, which should exit the program
    with patch('os.environ.get', return_value="sk-test-key"):
        with patch('main.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            from openai import AuthenticationError
            mock_client.chat.completions.create.side_effect = AuthenticationError(
                message="Invalid API Key",
                response=MagicMock(),
                body={}
            )

            with patch('builtins.input', side_effect=["hello"]):
                with patch('sys.exit', side_effect=SystemExit) as mock_exit:
                    with patch('builtins.print') as mock_print:
                        with pytest.raises(SystemExit):
                            main.main()
                        mock_print.assert_any_call("AI: Authentication Error: The API key starting with 'sk-t' is invalid or expired. Invalid API Key")
                        mock_exit.assert_called_once_with(1)
