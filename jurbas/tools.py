"""File-system and shell tools that the agent can invoke."""

import os
import shutil
import subprocess

try:
    from duckduckgo_search import DDGS
    HAS_WEB_SEARCH = True
except ImportError:
    HAS_WEB_SEARCH = False



from .security import ALLOWED_BASE, safe_path, is_secret_path, _is_dangerous

# ─── BASH timeout constant ───
BASH_TIMEOUT = 300


# ─── File tools ───

def read_file(file_path: str) -> str:
    """Read file content with security checks, redacting env secrets."""
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

    The command runs inside the repository directory with a 300-second timeout.
    Dangerous commands (rm -rf /, sudo, mkfs, etc.) are blocked for safety.
    """
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
            stdin=subprocess.DEVNULL,
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


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo (no API key required).

    Returns a list of search results with title, URL, and snippet for each.
    """
    import main
    if not getattr(main, "HAS_WEB_SEARCH", False):
        return (
            "Error: 'duckduckgo_search' library is not installed. "
            "Install it with: uv add duckduckgo-search  (or pip install duckduckgo-search)"
        )
    if not isinstance(query, str) or not query.strip():
        return "Error: query must be a non-empty string."
    if not isinstance(max_results, int) or max_results < 1 or max_results > 20:
        max_results = 5

    try:
        ddgs_class = getattr(main, "DDGS")
        with ddgs_class() as ddgs:
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
            # Truncate long snippets for readability
            snippet = (snippet[:300] + "...") if len(snippet) > 300 else snippet
            lines.append(f"   {snippet}")
        lines.append("")

    return "\n".join(lines).strip()


# ─── Handler registry ───

TOOL_HANDLERS = {
    "read_file":      lambda args: read_file(args["file_path"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "write_file":     lambda args: write_file(args["file_path"], args["content"]),
    "run_bash":       lambda args: run_bash(args["command"]),
    "web_search":     lambda args: web_search(args["query"], args.get("max_results", 5)),
}
