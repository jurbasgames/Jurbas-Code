"""Tests for Jurbas-Code (modular architecture)."""

import os
from pathlib import Path
import subprocess
import sys
import tomllib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import patch, MagicMock

import main
import jurbas.security
import jurbas.tools


@pytest.fixture(autouse=True)
def clean_history():
    """Ensure history.json is removed before and after every test to keep test isolation."""
    for filename in ("history.json", "history.json.bak"):
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError:
                pass
    yield
    for filename in ("history.json", "history.json.bak"):
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════
# safe_path()
# ═══════════════════════════════════════════════════════════════════════

def test_safe_path_relative_resolves_against_allowed_base():
    """A relative path is joined with ALLOWED_BASE before resolution."""
    resolved = jurbas.security.safe_path("sub/file.txt")
    assert resolved.startswith(jurbas.security.ALLOWED_BASE)


def test_safe_path_outside_raises():
    """An absolute path outside ALLOWED_BASE raises PermissionError."""
    with pytest.raises(PermissionError, match="Path not allowed"):
        jurbas.security.safe_path("//TMP/escaping.txt")


# ═══════════════════════════════════════════════════════════════════════
# is_secret_path()
# ═══════════════════════════════════════════════════════════════════════

def test_is_secret_path_true_for_dotenv():
    assert jurbas.security.is_secret_path(".env") is True
    assert jurbas.security.is_secret_path(".env.local") is True
    assert jurbas.security.is_secret_path("path/to/.env.production") is True


def test_is_secret_path_false_for_normal_file():
    assert jurbas.security.is_secret_path("main.py") is False
    assert jurbas.security.is_secret_path("README.md") is False


def test_is_secret_path_true_for_private_key():
    assert jurbas.security.is_secret_path("id_rsa") is True
    assert jurbas.security.is_secret_path("credentials.pem") is True


# ═══════════════════════════════════════════════════════════════════════
# load_dotenv()
# ═══════════════════════════════════════════════════════════════════════

@patch("jurbas.security.safe_path")
@patch.dict("os.environ", {}, clear=True)
def test_load_dotenv_sets_vars(mock_safe_path, tmp_path):
    """A simple .env file populates os.environ."""
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nBAZ=qux\n")
    mock_safe_path.return_value = str(env_file)

    jurbas.security.load_dotenv(str(env_file))

    assert os.environ.get("FOO") == "bar"
    assert os.environ.get("BAZ") == "qux"


@patch("jurbas.security.safe_path")
@patch.dict("os.environ", {"EXISTING": "keep"}, clear=True)
def test_load_dotenv_does_not_overwrite(mock_safe_path, tmp_path):
    """Existing env vars are NOT overwritten by .env."""
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING=overwrite\nNEW=added\n")
    mock_safe_path.return_value = str(env_file)

    jurbas.security.load_dotenv(str(env_file))

    assert os.environ["EXISTING"] == "keep"


# ═══════════════════════════════════════════════════════════════════════
# read_file()
# ═══════════════════════════════════════════════════════════════════════

@patch("jurbas.tools.safe_path")
@patch("os.path.exists")
@patch("builtins.open", new_callable=MagicMock)
def test_read_file_success(mock_open, mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = True

    mock_file = MagicMock()
    mock_file.read.return_value = "file content"
    mock_open.return_value.__enter__.return_value = mock_file

    assert jurbas.tools.read_file("test.txt") == "file content"
    mock_open.assert_called_once_with("/allowed/test.txt", "r", encoding="utf-8")


@patch("jurbas.tools.safe_path")
def test_read_file_permission_error(mock_safe_path):
    mock_safe_path.side_effect = PermissionError("Path not allowed: test.txt")
    assert "Error: Path not allowed: test.txt" in jurbas.tools.read_file("test.txt")


@patch("jurbas.tools.safe_path")
@patch("os.path.exists")
def test_read_file_not_found(mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = False
    assert "Error: file 'test.txt' not found." in jurbas.tools.read_file("test.txt")


# ═══════════════════════════════════════════════════════════════════════
# list_directory()
# ═══════════════════════════════════════════════════════════════════════

@patch("jurbas.tools.safe_path")
@patch("os.path.exists")
@patch("os.path.isdir")
@patch("os.listdir")
@patch("os.path.getsize")
def test_list_directory_success(mock_getsize, mock_listdir, mock_isdir,
                                mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/dir"
    mock_exists.return_value = True

    def isdir_side_effect(path):
        if path == "/allowed/dir":
            return True
        if path.endswith("subdir"):
            return True
        return False
    mock_isdir.side_effect = isdir_side_effect

    mock_listdir.return_value = ["file1.txt", "subdir"]
    mock_getsize.return_value = 1024  # 1.0 KB

    result = jurbas.tools.list_directory("dir")

    assert "Contents of 'dir' (2 items):" in result
    assert "[FILE] file1.txt (1.0 KB)" in result
    assert "[DIR] subdir" in result


@patch("jurbas.tools.safe_path", side_effect=PermissionError("Path not allowed"))
def test_list_directory_permission_error(mock_safe_path):
    result = jurbas.tools.list_directory("bad")
    assert "Error: Path not allowed" in result


@patch("jurbas.tools.safe_path", return_value="/allowed/missing")
def test_list_directory_not_found(mock_safe_path):
    with patch("os.path.exists", return_value=False):
        result = jurbas.tools.list_directory("missing")
    assert "Error: directory 'missing' not found." in result


@patch("jurbas.tools.safe_path", return_value="/allowed/file.txt")
def test_list_directory_not_a_dir(mock_safe_path):
    with patch("os.path.exists", return_value=True):
        with patch("os.path.isdir", return_value=False):
            result = jurbas.tools.list_directory("file.txt")
    assert "Error: 'file.txt' is not a directory." in result


# ═══════════════════════════════════════════════════════════════════════
# write_file()
# ═══════════════════════════════════════════════════════════════════════

@patch("jurbas.tools.safe_path")
@patch("jurbas.tools.os.makedirs")
@patch("jurbas.tools.os.path.exists")
@patch("jurbas.tools.shutil.copy2")
@patch("jurbas.tools.os.path.getsize")
def test_write_file_success(mock_getsize, mock_copy2, mock_exists,
                            mock_makedirs, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = False  # No backup needed
    mock_getsize.return_value = 12

    with patch("builtins.open", MagicMock()) as mock_open:
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        result = jurbas.tools.write_file("test.txt", "file content")

    mock_makedirs.assert_called_once_with("/allowed", exist_ok=True)
    mock_open.assert_called_once_with("/allowed/test.txt", "w", encoding="utf-8")
    mock_file.write.assert_called_once_with("file content")
    mock_copy2.assert_not_called()
    assert "written successfully (12 bytes)" in result


@patch("jurbas.tools.safe_path")
@patch("jurbas.tools.os.makedirs")
@patch("jurbas.tools.os.path.exists")
@patch("jurbas.tools.shutil.copy2")
@patch("jurbas.tools.os.path.getsize")
def test_write_file_with_backup(mock_getsize, mock_copy2, mock_exists,
                                mock_makedirs, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = True   # Needs backup
    mock_getsize.return_value = 12

    with patch("builtins.open", MagicMock()):
        result = jurbas.tools.write_file("test.txt", "file content")

    mock_copy2.assert_called_once_with("/allowed/test.txt",
                                       "/allowed/test.txt.bak")
    assert "previous version backed up to 'test.txt.bak'" in result


@patch("jurbas.tools.safe_path", side_effect=PermissionError("Path not allowed"))
def test_write_file_permission_error(mock_safe_path):
    result = jurbas.tools.write_file("bad.txt", "content")
    assert "Error: Path not allowed" in result


# ═══════════════════════════════════════════════════════════════════════
# run_bash()
# ═══════════════════════════════════════════════════════════════════════

@patch("jurbas.tools.subprocess.run")
def test_run_bash_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "hello world\n"
    mock_result.stderr = ""
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = jurbas.tools.run_bash("echo hello")
    assert "hello world" in result


@patch("jurbas.tools.subprocess.run", side_effect=Exception("Boom"))
def test_run_bash_error(mock_run):
    result = jurbas.tools.run_bash("fail")
    assert "Error executing command" in result


# ═══════════════════════════════════════════════════════════════════════
# main() loop  (streaming-based)
# ═══════════════════════════════════════════════════════════════════════

def _make_stream_chunks(*text_fragments: str):
    """Helper: yield minimal SSE-like chunks for streaming tests."""
    for frag in text_fragments:
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = frag
        chunk.choices[0].delta.role = None
        chunk.choices[0].delta.reasoning_content = None
        chunk.choices[0].delta.tool_calls = None
        yield chunk


@patch("openai.OpenAI")
@patch("builtins.input")
@patch("builtins.print")
def test_main_loop_exit(mock_print, mock_input, mock_openai):
    """Exiting immediately should not call the API."""
    mock_input.return_value = "exit"
    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-test"}):
        main.main(args=[])
    mock_openai.assert_called_once()
    ai_prints = [c for c in mock_print.call_args_list
                 if c.args and "AI:" in str(c.args[0])]
    assert len(ai_prints) == 0


def test_cli_startup_does_not_run_git_analysis():
    """Interactive startup must not run repository analysis or write git reports."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    git_objects_path = os.path.join(repo_root, "_git_objects.txt")
    git_analysis_path = os.path.join(repo_root, "_git_analysis.txt")
    for path in (git_objects_path, git_analysis_path):
        if os.path.exists(path):
            os.remove(path)

    env = os.environ.copy()
    env.update({"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-test"})
    result = subprocess.run(
        [sys.executable, "main.py"],
        input="exit\n",
        text=True,
        capture_output=True,
        cwd=repo_root,
        env=env,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    combined_output = result.stdout + result.stderr
    assert "EXTRAÇÃO DE OBJETOS GIT" not in combined_output
    assert "Auto-extract" not in combined_output
    assert "analyze_pr" not in combined_output
    assert not os.path.exists(git_objects_path)
    assert not os.path.exists(git_analysis_path)


@patch("openai.OpenAI")
@patch("builtins.input")
@patch("builtins.print")
def test_main_loop_streams_content(mock_print, mock_input, mock_openai):
    """A non-tool streaming response is printed."""
    mock_input.side_effect = ["hello", "exit"]

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_stream_chunks(
        "Hello ", "world!"
    )

    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-test"}):
        main.main(args=[])

    print_text = "".join(str(c.args[0]) for c in mock_print.call_args_list
                         if c.args)
    assert "Hello" in print_text
    assert "world" in print_text


@patch("openai.OpenAI")
@patch("builtins.input")
@patch("builtins.print")
@patch("jurbas.tools.read_file")
def test_main_loop_with_tool_call(mock_read_file, mock_print,
                                  mock_input, mock_openai):
    """A tool-call in the stream leads to tool execution."""
    mock_input.side_effect = ["read something", "exit"]

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    def _chunk(content=None, tool_calls=None, finish_reason=None):
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = content
        choice.delta.role = None
        choice.delta.reasoning_content = None
        choice.delta.tool_calls = tool_calls
        choice.finish_reason = finish_reason
        chunk.choices = [choice]
        return chunk

    # Tool call that says "read_file"
    tool_call = MagicMock()
    tool_call.index = 0
    tool_call.id = "call_abc"
    tool_call.type = "function"
    func = MagicMock()
    func.name = "read_file"
    func.arguments = '{"file_path": "test.txt"}'
    tool_call.function = func

    mock_client.chat.completions.create.side_effect = [
        iter([
            _chunk(content="", tool_calls=None),
            _chunk(content=None, tool_calls=[tool_call],
                   finish_reason="tool_calls"),
        ]),
        iter([_chunk(content="Here is the result")]),
    ]

    mock_read_file.return_value = "mocked content"

    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-test"}):
        main.main(args=[])

    mock_read_file.assert_called_once_with("test.txt")
    print_text = "".join(str(c.args[0]) for c in mock_print.call_args_list
                         if c.args)
    assert "Here is the result" in print_text


# ═══════════════════════════════════════════════════════════════════════
# Extra safety & error handling tests
# ═══════════════════════════════════════════════════════════════════════

@patch('builtins.print')
def test_main_missing_deepseek_api_key(mock_print):
    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "   "}):
        with patch('sys.exit', side_effect=SystemExit) as mock_exit:
            with pytest.raises(SystemExit):
                main.main(args=[])
            mock_exit.assert_called_once_with(1)
            mock_print.assert_any_call("Error: DEEPSEEK_API_KEY environment variable is not set or is empty.")


@patch('openai.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
def test_main_authentication_error_exits(mock_print, mock_input, mock_openai):
    from openai import AuthenticationError

    mock_input.side_effect = ["hello"]
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    err = AuthenticationError("Invalid API Key", response=MagicMock(), body={})
    mock_client.chat.completions.create.side_effect = err

    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-123456789"}):
        with patch('sys.exit', side_effect=SystemExit) as mock_exit:
                with pytest.raises(SystemExit):
                    main.main(args=[])
                mock_exit.assert_called_once_with(1)
                mock_print.assert_any_call("AI: Authentication Error: The API key starting with 'sk-1' is invalid or expired. Invalid API Key")


@patch('openai.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
def test_main_api_error_drops_turn(mock_print, mock_input, mock_openai):
    from openai import APIError

    mock_input.side_effect = ["hello", "retry_hello", "quit"]
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    err = APIError("Rate limit exceeded", request=MagicMock(), body={})

    # The second response chunk generator
    def _chunk_stream():
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = "Success response"
        choice.delta.role = "assistant"
        choice.delta.reasoning_content = None
        choice.delta.tool_calls = None
        chunk.choices = [choice]
        chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        yield chunk

    mock_client.chat.completions.create.side_effect = [err, _chunk_stream()]

    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-test"}):
        main.main(args=[])

        assert mock_client.chat.completions.create.call_count == 2
        
        second_call_kwargs = mock_client.chat.completions.create.call_args_list[1][1]
        contents = [m["content"] for m in second_call_kwargs["messages"] if m["role"] == "user"]
        assert "hello" not in contents
        assert "retry_hello" in contents


@patch('openai.OpenAI')
@patch('builtins.input')
@patch('builtins.print')
def test_main_read_file_env_redacted(mock_print, mock_input, mock_openai):
    mock_input.side_effect = ["read env", "quit"]
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # First call: returns a tool call for read_file targeting .env
    def _tool_call_stream():
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = ""
        choice.delta.role = "assistant"
        choice.delta.reasoning_content = None
        
        tool_call = MagicMock()
        tool_call.index = 0
        tool_call.id = "call_env"
        tool_call.type = "function"
        func = MagicMock()
        func.name = "read_file"
        func.arguments = '{"file_path": ".env"}'
        tool_call.function = func
        
        choice.delta.tool_calls = [tool_call]
        chunk.choices = [choice]
        yield chunk

    # Second call: returns text response
    def _text_response_stream():
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = "I read it"
        choice.delta.role = "assistant"
        choice.delta.reasoning_content = None
        choice.delta.tool_calls = None
        chunk.choices = [choice]
        chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        yield chunk

    mock_client.chat.completions.create.side_effect = [_tool_call_stream(), _text_response_stream()]

    with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-test"}):
        main.main(args=[])

    call_kwargs = mock_client.chat.completions.create.call_args_list[1][1]
    tool_result = [m for m in call_kwargs["messages"] if m["role"] == "tool"][0]
    assert "<REDACTED: .env content is hidden from model for security>" in tool_result["content"]


# ═══════════════════════════════════════════════════════════════════════
# Versioning (issue #9)
# ═══════════════════════════════════════════════════════════════════════

def test_version_attribute_is_nonempty_string():
    import jurbas
    assert isinstance(jurbas.__version__, str) and jurbas.__version__
    assert main.__version__ == jurbas.__version__


def test_source_checkout_version_fallback_reads_pyproject():
    import jurbas

    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert jurbas._read_version_from_pyproject() == pyproject["project"]["version"]


def test_main_version_flag_exits_zero_and_prints(capsys):
    with pytest.raises(SystemExit) as exc:
        main.main(args=["--version"])
    assert exc.value.code == 0
    assert f"Jurbas-Code v{main.__version__}" in capsys.readouterr().out


def test_main_version_short_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main.main(args=["-v"])
    assert exc.value.code == 0
    assert f"Jurbas-Code v{main.__version__}" in capsys.readouterr().out


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
