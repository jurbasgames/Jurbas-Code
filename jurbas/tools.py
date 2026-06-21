import os
import shutil
import subprocess
from .security import safe_path, BASH_TIMEOUT, ALLOWED_BASE

def read_file(file_path: str) -> str:
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(full):
        return f"Error: file '{file_path}' not found."
    try:
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def list_directory(dir_path: str) -> str:
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
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
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
    """Execute a bash command inside the project directory and return its output.

    Use this for git operations, running scripts, installing dependencies,
    or any shell-level task. The command runs in './' (ALLOWED_BASE) as working
    directory with a {BASH_TIMEOUT}s timeout.

    Dangerous commands (rm -rf /, sudo, mkfs, etc.) are blocked for safety.
    """
    from .security import _is_dangerous
    if not isinstance(command, str):
        return "Error: command must be a string."
    reason = _is_dangerous(command)
    if reason:
        return f"Error: {reason}"
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=ALLOWED_BASE,
            timeout=BASH_TIMEOUT,
            shell=True,
            executable="/bin/bash",
        )
        output_parts = []
        if result.stdout.strip():
            output_parts.append(result.stdout.rstrip("\n"))
        if result.stderr.strip():
            output_parts.append(f"[stderr]\n{result.stderr.rstrip()}")
        if not output_parts:
            if result.returncode == 0:
                return "(command completed with no output)"
            else:
                return f"Error: command failed (exit code {result.returncode}) with no output."
        output = "\n".join(output_parts)
        if result.returncode != 0:
            return f"Command exited with code {result.returncode}.\n{output}"
        return output
    except FileNotFoundError:
        return "Error: shell (/bin/bash) not found."
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {BASH_TIMEOUT}s."
    except PermissionError:
        return "Error: permission denied while running command."
    except Exception as e:
        return f"Error executing command: {e}"

TOOL_HANDLERS = {
    "read_file": lambda args: read_file(args["file_path"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "write_file": lambda args: write_file(args["file_path"], args["content"]),
    "run_bash": lambda args: run_bash(args["command"]),
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a text file.",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "File path (e.g.: './main.py')."}},
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {"dir_path": {"type": "string", "description": "Directory path (e.g.: './' for project root)."}},
                "required": ["dir_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a file. Creates parent directories if needed. Use to modify your own code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path of the file to be written."},
                    "content": {"type": "string", "description": "Complete content to be written to the file."}
                },
                "required": ["file_path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": f"Execute a bash command inside the project directory. Timeout is {BASH_TIMEOUT}s. Dangerous commands are blocked.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "The bash command to execute."}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]
