"""File-system and shell tools that the agent can invoke."""

import os
import shutil
import subprocess

from .security import ALLOWED_BASE, safe_path, is_secret_path


# ─── File tools ───

def read_file(file_path: str) -> str:
    """Read file content with security checks."""
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if is_secret_path(full):
        return f"Error: reading secret file '{file_path}' is not allowed."
    if not os.path.exists(full):
        return f"Error: file '{file_path}' not found."
    try:
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(dir_path: str) -> str:
    """Lists files and folders in the specified directory."""
    try:
        full = safe_path(dir_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(full):
        return f"Error: directory '{dir_path}' not found."
    if not os.path.isdir(full):
        return f"Error: '{dir_path}' is not a directory."
    try:
        items = []
        for name in sorted(os.listdir(full)):
            item_path = os.path.join(full, name)
            kind = "DIR" if os.path.isdir(item_path) else "FILE"
            size = ""
            if kind == "FILE":
                try:
                    size_bytes = os.path.getsize(item_path)
                    if size_bytes < 1024:
                        size = f" ({size_bytes} B)"
                    elif size_bytes < 1024 * 1024:
                        size = f" ({size_bytes / 1024:.1f} KB)"
                    else:
                        size = f" ({size_bytes / 1024 / 1024:.1f} MB)"
                except OSError:
                    size = " (unknown size)"

            items.append(f"  [{kind}] {name}{size}")
        return f"Contents of '{dir_path}' ({len(items)} items):\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {e}"


def write_file(file_path: str, content: str) -> str:
    """Writes content to a file (creates parent directories if needed)."""
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        # Back up an existing file before overwriting so a bad generation
        # (e.g. self-modifying main.py) can be recovered.
        backup_note = ""
        if os.path.exists(full):
            backup = full + ".bak"
            shutil.copy2(full, backup)
            backup_note = f" (previous version backed up to '{os.path.basename(backup)}')"
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(full)
        return f"File '{file_path}' written successfully ({size} bytes).{backup_note}"
    except Exception as e:
        return f"Error writing file: {e}"


def run_bash(command: str) -> str:
    """Executes a shell command in the project root and returns stdout + stderr.

    The command runs inside the repository directory with a 60-second timeout.
    Use this for git operations, running tests, or any CLI tool.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ALLOWED_BASE,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n--- stderr ---\n"
            output += result.stderr
        if not output:
            output = "(no output)"
        return output.strip()
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {e}"


# ─── Handler registry ───

TOOL_HANDLERS = {
    "read_file":      lambda args: read_file(args["file_path"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "write_file":     lambda args: write_file(args["file_path"], args["content"]),
    "run_bash":       lambda args: run_bash(args["command"]),
}
