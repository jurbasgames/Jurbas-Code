import pytest
from unittest.mock import patch, MagicMock
import os
import shutil
import subprocess
from jurbas_code import tools

# === TESTS FOR safe_path() ===
def test_safe_path_allowed():
    # Test path resolution inside ALLOWED_BASE
    with patch('os.path.realpath', side_effect=lambda x: os.path.abspath(x)):
        with patch('os.path.commonpath', return_value=os.path.abspath(tools.ALLOWED_BASE)):
             assert tools.safe_path("test.txt") == os.path.abspath("test.txt")

def test_safe_path_denied():
    # Test path resolution outside ALLOWED_BASE
    with patch('os.path.realpath', return_value="/tmp/test.txt"):
        with patch('os.path.commonpath', return_value="/tmp"):
            with pytest.raises(PermissionError) as exc_info:
                tools.safe_path("../../../tmp/test.txt")
            assert "Path not allowed" in str(exc_info.value)

# === TESTS FOR read_file() ===
@patch('jurbas_code.tools.safe_path')
@patch('os.path.exists')
@patch('builtins.open', new_callable=MagicMock)
def test_read_file_success(mock_open, mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = True

    # Mocking open().read()
    mock_file = MagicMock()
    mock_file.read.return_value = "file content"
    mock_open.return_value.__enter__.return_value = mock_file

    assert tools.read_file("test.txt") == "file content"
    mock_open.assert_called_once_with("/allowed/test.txt", "r", encoding="utf-8")

@patch('jurbas_code.tools.safe_path')
def test_read_file_permission_error(mock_safe_path):
    mock_safe_path.side_effect = PermissionError("Path not allowed: test.txt")
    assert "Error: Path not allowed: test.txt" in tools.read_file("test.txt")

@patch('jurbas_code.tools.safe_path')
@patch('os.path.exists')
def test_read_file_not_found(mock_exists, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_exists.return_value = False
    assert "Error: file 'test.txt' not found." in tools.read_file("test.txt")

# === TESTS FOR list_directory() ===
@patch('jurbas_code.tools.safe_path')
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

    result = tools.list_directory("dir")

    assert "Contents of 'dir' (2 items):" in result
    assert "[FILE] file1.txt (1.0 KB)" in result
    assert "[DIR] subdir" in result

@patch('jurbas_code.tools.safe_path')
def test_list_directory_permission_error(mock_safe_path):
    mock_safe_path.side_effect = PermissionError("Path not allowed")
    assert "Error: Path not allowed" in tools.list_directory("dir")

# === TESTS FOR write_file() ===
@patch('jurbas_code.tools.safe_path')
@patch('os.makedirs')
@patch('os.path.getsize')
@patch('builtins.open', new_callable=MagicMock)
def test_write_file_success(mock_open, mock_getsize, mock_makedirs, mock_safe_path):
    mock_safe_path.return_value = "/allowed/test.txt"
    mock_getsize.return_value = 12

    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file

    result = tools.write_file("test.txt", "file content")

    mock_makedirs.assert_called_once_with("/allowed", exist_ok=True)
    mock_open.assert_called_once_with("/allowed/test.txt", "w", encoding="utf-8")
    mock_file.write.assert_called_once_with("file content")
    assert "written successfully (12 bytes)" in result

# === BASH & SAFETY TESTS ===
def test_is_dangerous():
    assert tools._is_dangerous("ls | sudo tee file") is not None
    assert tools._is_dangerous("cat file | bash") is not None
    assert tools._is_dangerous("ls | grep something") is None

def test_is_readonly_bash():
    assert tools._is_readonly_bash("ls -la") is True
    assert tools._is_readonly_bash("rm -rf /") is False
    assert tools._is_readonly_bash("ls -la && echo ok") is False

def test_requires_confirmation():
    assert tools._requires_confirmation("write_file", {"file_path": "a.txt", "content": "a"}) is True
    assert tools._requires_confirmation("run_bash", {"command": "ls"}) is False
    assert tools._requires_confirmation("run_bash", {"command": "rm -rf /"}) is True

@patch('builtins.input', return_value='y')
def test_confirm_action(mock_input):
    assert tools.confirm_action("run_bash", {"command": "ls"}) is True

def test_run_bash_non_string():
    assert tools.run_bash(123) == "Error: command must be a string."
