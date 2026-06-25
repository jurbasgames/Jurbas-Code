"""Filesystem, bash execution, and web search tools for the agent."""

import os
import shutil
import subprocess

from jurbas_code.security import (
    ALLOWED_BASE,
    safe_path,
    is_secret_path,
    load_dotenv,
    _is_dangerous,
    _is_readonly_bash,
    _requires_confirmation,
    confirm_action,
)

DDGS = None
try:
    from ddgs import DDGS as _DDGS
    DDGS = _DDGS
    HAS_WEB_SEARCH = True
except ImportError:
    try:
        from duckduckgo_search import DDGS as _DDGS
        DDGS = _DDGS
        HAS_WEB_SEARCH = True
    except ImportError:
        DDGS = None
        HAS_WEB_SEARCH = False

BASH_TIMEOUT = 300


def read_file(file_path: str) -> str:
    if not isinstance(file_path, str):
        return "Error: file_path must be a string."
    if ".env" in file_path:
        return "<REDACTED: .env content is hidden from model for security>"
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if is_secret_path(full):
        return "<REDACTED: .env content is hidden from model for security>"
    if not os.path.exists(full):
        return f"Error: file '{file_path}' not found."
    if os.path.isdir(full):
        return f"Error: '{file_path}' is a directory, not a file."
    try:
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(dir_path: str) -> str:
    if not isinstance(dir_path, str):
        return "Error: dir_path must be a string."
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
    if not isinstance(file_path, str):
        return "Error: file_path must be a string."
    if not isinstance(content, str):
        return "Error: content must be a string."
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if os.path.isdir(full):
        return f"Error: '{file_path}' is a directory."
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


class ShellHealth:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_signal = ""

    def record_result(self, command: str, exit_code: int, stderr: str) -> str | None:
        """Returns diagnostic message if broken, None otherwise."""
        if exit_code == 0:
            self.reset()
            return None

        stderr_lower = (stderr or "").lower()
        known_signals = [
            "não tem distribuições instaladas",
            "no distributions installed",
            "command not found",
            "not recognized",
        ]

        matched = False
        for signal in known_signals:
            if signal in stderr_lower:
                self.consecutive_failures += 1
                self.last_signal = signal
                matched = True
                break

        if not matched:
            self.reset()
            return None

        if self.is_broken():
            return f"\n[Diagnostic] Shell might be broken: {self.consecutive_failures} consecutive known failures. Last signal: '{self.last_signal}'"

        return None

    def reset(self) -> None:
        self.consecutive_failures = 0
        self.last_signal = ""

    def is_broken(self) -> bool:
        return self.consecutive_failures >= 3


# Global ShellHealth manager instance to track state correctly
shell_health = ShellHealth()


def run_bash(command: str) -> str:
    from jurbas_code.security import _SHELL_EXECUTABLE
    if not isinstance(command, str):
        return "Error: command must be a string."
    reason = _is_dangerous(command)
    if reason:
        return f"Error: {reason}"
    try:
        kwargs = dict(
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            cwd=ALLOWED_BASE,
            timeout=BASH_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
        if _SHELL_EXECUTABLE:
            result = subprocess.run([_SHELL_EXECUTABLE, "-c", command], shell=False, **kwargs)
        else:
            result = subprocess.run(command, shell=True, **kwargs)

        diag = shell_health.record_result(command, result.returncode, result.stderr)

        output_parts = []
        if result.stdout.strip():
            output_parts.append(result.stdout.rstrip("\n"))
        if result.stderr.strip():
            output_parts.append(f"[stderr]\n{result.stderr.rstrip()}")
        if not output_parts:
            if result.returncode == 0:
                output = "(command completed with no output)"
            else:
                output = f"Error: command failed (exit code {result.returncode}) with no output."
        else:
            output = "\n".join(output_parts)
            if result.returncode != 0:
                output = f"Command exited with code {result.returncode}.\n{output}"

        if diag:
            output += diag
        return output
    except FileNotFoundError:
        from jurbas_code.security import _IS_WINDOWS
        shell_name = "cmd.exe" if _IS_WINDOWS else (_SHELL_EXECUTABLE or "shell")
        return f"Error: shell ({shell_name}) not found."
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {BASH_TIMEOUT}s."
    except PermissionError:
        return "Error: permission denied while running command."
    except Exception as e:
        return f"Error executing command: {e}"


def web_search(query: str, max_results: int = 5) -> str:
    if not HAS_WEB_SEARCH or DDGS is None:
        return (
            "Error: 'duckduckgo_search' library is not installed. "
            "Install it with: uv add ddgs  (or pip install ddgs)"
        )
    if not isinstance(query, str) or not query.strip():
        return "Error: query must be a non-empty string."
    if not isinstance(max_results, int) or max_results < 1 or max_results > 20:
        max_results = 5
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"Error performing web search: {e}"
    if not results:
        return f"No results found for '{query}'."
    lines = [f"Web search results for '{query}':\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "(no title)").strip()
        href = r.get("href", r.get("link", "")).strip()
        snippet = r.get("body", r.get("snippet", "")).strip()
        lines.append(f"{i}. {title}")
        if href:
            lines.append(f"   URL: {href}")
        if snippet:
            snippet = (snippet[:300] + "...") if len(snippet) > 300 else snippet
            lines.append(f"   {snippet}")
        lines.append("")
    return "\n".join(lines).strip()


TOOL_HANDLERS = {
    "read_file": lambda args: read_file(args["file_path"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "write_file": lambda args: write_file(args["file_path"], args["content"]),
    "run_bash": lambda args: run_bash(args["command"]),
    "web_search": lambda args: web_search(args["query"], args.get("max_results", 5)),
}
