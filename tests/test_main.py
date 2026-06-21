"""Tests for Jurbas-Code (modular architecture)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import patch, MagicMock

import main
import jurbas.security
import jurbas.tools


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
    assert os.environ.get("NEW") == "added"


@patch("jurbas.security.safe_path")
@patch.dict("os.environ", {}, clear=True)
def test_load_dotenv_handles_export_prefix(mock_safe_path, tmp_path):
    """Lines starting with 'export ' are handled correctly."""
    env_file = tmp_path / ".env"
    env_file.write_text("export MY_KEY=my_value\n")
    mock_safe_path.return_value = str(env_file)

    jurbas.security.load_dotenv(str(env_file))

    assert os.environ.get("MY_KEY") == "my_value"


@patch("jurbas.security.safe_path")
@patch.dict("os.environ", {}, clear=True)
def test_load_dotenv_skips_comments_and_blanks(mock_safe_path, tmp_path):
    """Comment lines and blank lines are ignored."""
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\n\nFOO=bar\n")
    mock_safe_path.return_value = str(env_file)

    jurbas.security.load_dotenv(str(env_file))

    assert os.environ.get("FOO") == "bar"


# ═══════════════════════════════════════════════════════════════════════
# read_file()
# ═══════════════════════════════════════════════════════════════════════

@patch("jurbas.tools.safe_path")
@patch("jurbas.tools.is_secret_path", return_value=False)
def test_read_file_success(mock_secret, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"

    with patch("builtins.open", MagicMock()) as mock_open:
        mock_file = MagicMock()
        mock_file.read.return_value = "file content"
        mock_open.return_value.__enter__.return_value = mock_file
        with patch("os.path.exists", return_value=True):
            result = jurbas.tools.read_file("test.txt")

    assert result == "file content"
    mock_open.assert_called_once_with("/allowed/test.txt", "r", encoding="utf-8")


def test_read_file_secret_denied():
    """Reading a secret-file path returns an error, not the content."""
    result = jurbas.tools.read_file(".env")
    assert "Error: reading secret file" in result
    assert ".env" in result


@patch("jurbas.tools.safe_path", side_effect=PermissionError("Path not allowed"))
def test_read_file_permission_error(mock_safe_path):
    result = jurbas.tools.read_file("bad.txt")
    assert "Error: Path not allowed" in result


@patch("jurbas.tools.safe_path", return_value="/allowed/missing.txt")
def test_read_file_not_found(mock_safe_path):
    with patch("os.path.exists", return_value=False):
        result = jurbas.tools.read_file("missing.txt")
    assert "Error: file 'missing.txt' not found." in result


# ═══════════════════════════════════════════════════════════════════════
# list_directory()
# ═══════════════════════════════════════════════════════════════════════

@patch("jurbas.tools.safe_path")
@patch("jurbas.tools.os.path.exists")
@patch("jurbas.tools.os.path.isdir")
@patch("jurbas.tools.os.listdir")
@patch("jurbas.tools.os.path.getsize")
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
    mock_getsize.return_value = 1024

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


@patch("main.OpenAI")
@patch("builtins.input")
@patch("builtins.print")
def test_main_loop_exit(mock_print, mock_input, mock_openai):
    """Exiting immediately should not call the API."""
    mock_input.return_value = "exit"
    main.main()
    mock_openai.assert_called_once()
    ai_prints = [c for c in mock_print.call_args_list
                 if c.args and "AI:" in str(c.args[0])]
    assert len(ai_prints) == 0


@patch("main.OpenAI")
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

    main.main()

    print_text = "".join(str(c.args[0]) for c in mock_print.call_args_list
                         if c.args)
    assert "Hello" in print_text
    assert "world" in print_text


@patch("main.OpenAI")
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

    main.main()

    mock_read_file.assert_called_once_with("test.txt")
    print_text = "".join(str(c.args[0]) for c in mock_print.call_args_list
                         if c.args)
    assert "Here is the result" in print_text
