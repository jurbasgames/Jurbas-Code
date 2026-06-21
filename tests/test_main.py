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

# === TESTS FOR web_search() ===
class TestWebSearch:
    """Tests for the web_search tool using DuckDuckGo."""

    def test_missing_library(self):
        """Graceful message when duckduckgo_search is not installed."""
        with patch('main.HAS_WEB_SEARCH', False):
            result = main.web_search("test query")
            assert "not installed" in result
            assert "duckduckgo-search" in result

    def test_empty_query(self):
        """Empty or whitespace query should be rejected."""
        with patch('main.HAS_WEB_SEARCH', True):
            assert "non-empty string" in main.web_search("")
            assert "non-empty string" in main.web_search("   ")

    def test_non_string_query(self):
        """Non-string query should be rejected."""
        with patch('main.HAS_WEB_SEARCH', True):
            assert "non-empty string" in main.web_search(123)
            assert "non-empty string" in main.web_search(None)
            assert "non-empty string" in main.web_search([])

    @patch('main.DDGS')
    def test_max_results_clamped_low(self, mock_ddgs_class):
        """max_results < 1 should be clamped to default 5."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = []

            main.web_search("python", max_results=0)
            mock_instance.text.assert_called_with("python", max_results=5)

    @patch('main.DDGS')
    def test_max_results_clamped_high(self, mock_ddgs_class):
        """max_results > 20 should be clamped to default 5."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = []

            main.web_search("python", max_results=100)
            mock_instance.text.assert_called_with("python", max_results=5)

    @patch('main.DDGS')
    def test_successful_search(self, mock_ddgs_class):
        """Valid search returns formatted results."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = [
                {"title": "Pytest Docs", "href": "https://docs.pytest.org", "body": "Full pytest documentation."},
            ]

            result = main.web_search("pytest", max_results=1)

            assert "Web search results for 'pytest'" in result
            assert "1. Pytest Docs" in result
            assert "https://docs.pytest.org" in result
            assert "Full pytest documentation" in result
            mock_instance.text.assert_called_once_with("pytest", max_results=1)

    @patch('main.DDGS')
    def test_no_results(self, mock_ddgs_class):
        """Empty result list from DDGS."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = []

            result = main.web_search("nonexistent_xyz")
            assert "No results found" in result

    @patch('main.DDGS')
    def test_link_fallback(self, mock_ddgs_class):
        """Use 'link' key when 'href' is not present."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = [
                {"title": "Example", "link": "https://example.org", "body": "Example."},
            ]

            result = main.web_search("example", max_results=1)
            assert "https://example.org" in result

    @patch('main.DDGS')
    def test_snippet_truncation(self, mock_ddgs_class):
        """Long snippets are truncated at 300 characters."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            long_body = "A" * 500
            mock_instance.text.return_value = [
                {"title": "Long", "href": "https://long.com", "body": long_body},
            ]

            result = main.web_search("long", max_results=1)
            # Truncated to 300 chars + "..."
            assert "..." in result
            # Should not contain the full 500 chars
            assert long_body not in result

    @patch('main.DDGS')
    def test_api_error(self, mock_ddgs_class):
        """DDGS exception is caught and reported."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.side_effect = Exception("Rate limit exceeded")

            result = main.web_search("python")
            assert "Error performing web search" in result
            assert "Rate limit exceeded" in result

    @patch('main.DDGS')
    def test_multiple_results_formatting(self, mock_ddgs_class):
        """Multiple results are numbered and separated."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = [
                {"title": "Result A", "href": "https://a.com", "body": "First result."},
                {"title": "Result B", "href": "https://b.com", "body": "Second result."},
                {"title": "Result C", "href": "https://c.com", "body": "Third result."},
            ]

            result = main.web_search("test", max_results=3)

            assert result.count("\n   URL:") == 3  # Three URLs
            assert "1. Result A" in result
            assert "2. Result B" in result
            assert "3. Result C" in result
            mock_instance.text.assert_called_once_with("test", max_results=3)

    @patch('main.DDGS')
    def test_missing_fields_in_result(self, mock_ddgs_class):
        """Result with missing optional fields (title/href/body) should not crash."""
        with patch('main.HAS_WEB_SEARCH', True):
            mock_instance = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = [
                {},  # Completely empty result
                {"title": "Only Title"},  # Missing href and body
                {"href": "https://nolabel.com"},  # Missing title and body
            ]

            result = main.web_search("weird", max_results=3)
            # Should not crash; should handle gracefully
            assert "(no title)" in result or "Only Title" in result

# === TESTS FOR main() ===
@patch('main.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
def test_main_loop_exit(mock_print, mock_input, mock_openai):
    # Setup to exit immediately
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

    main.main()

    # Check if tool was actually called
    mock_read_file.assert_called_once_with("test.txt")

    # Check if AI's final text was printed
    mock_print.assert_any_call("AI: Here is the content\n")

    # Check token metrics printing
    mock_print.assert_any_call("  [Tokens] Request: 0p / 0c (0 total) | Session: 0p / 0c (0 total)")
    mock_print.assert_any_call("  [Tokens] Request: 20p / 10c (30 total) | Session: 20p / 10c (30 total)")
