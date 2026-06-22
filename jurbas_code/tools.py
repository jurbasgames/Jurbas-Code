"""Filesystem, bash execution, and web search tools for the agent."""

import os
import shutil
import subprocess
from jurbas.security import ALLOWED_BASE

BASH_TIMEOUT = 300

def _get_os():
    try:
        import jurbas.tools
        return jurbas.tools.os
    except (ImportError, AttributeError):
        return os

def _get_shutil():
    try:
        import jurbas.tools
        return jurbas.tools.shutil
    except (ImportError, AttributeError):
        return shutil

def _get_subprocess():
    try:
        import jurbas.tools
        return jurbas.tools.subprocess
    except (ImportError, AttributeError):
        return subprocess

def _real_safe_path(file_path: str) -> str:
    path = file_path or "."
    if os.path.isabs(path):
        full = os.path.realpath(path)
    else:
        full = os.path.realpath(os.path.join(ALLOWED_BASE, path))
    try:
        allowed_norm = os.path.normcase(ALLOWED_BASE)
        full_norm = os.path.normcase(full)
        if os.path.normcase(os.path.commonpath([allowed_norm, full_norm])) != allowed_norm:
            raise PermissionError(f"Path not allowed: {file_path}")
    except ValueError:
        raise PermissionError(f"Path not allowed: {file_path}")
    return full

def safe_path(file_path: str) -> str:
    try:
        import jurbas.tools
        f = jurbas.tools.safe_path
        if type(f).__name__ in ("MagicMock", "Mock") or f.__code__ != safe_path.__code__:
            return f(file_path)
    except (ImportError, AttributeError, NameError):
        pass
    return _real_safe_path(file_path)

def is_secret_path(file_path: str) -> bool:
    import jurbas.security
    return jurbas.security.is_secret_path(file_path)

def load_dotenv(file_path: str = ".env") -> None:
    import jurbas.security
    return jurbas.security.load_dotenv(file_path)

def _is_dangerous(command: str) -> str | None:
    import jurbas.security
    return jurbas.security._is_dangerous(command)

def _is_readonly_bash(command: str) -> bool:
    import jurbas.security
    return jurbas.security._is_readonly_bash(command)

def _requires_confirmation(name: str, args) -> bool:
    import jurbas.security
    return jurbas.security._requires_confirmation(name, args)

def confirm_action(name: str, args) -> bool:
    import jurbas.security
    return jurbas.security.confirm_action(name, args)

def read_file(file_path: str) -> str:
    os_mod = _get_os()
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
    if not os_mod.path.exists(full):
        return f"Error: file '{file_path}' not found."
    try:
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def list_directory(dir_path: str) -> str:
    os_mod = _get_os()
    try:
        full = safe_path(dir_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os_mod.path.exists(full):
        return f"Error: directory '{dir_path}' not found."
    if not os_mod.path.isdir(full):
        return f"Error: '{dir_path}' is not a directory."
    try:
        items = []
        for name in sorted(os_mod.listdir(full)):
            item_path = os_mod.path.join(full, name)
            kind = "DIR" if os_mod.path.isdir(item_path) else "FILE"
            size = ""
            if kind == "FILE":
                try:
                    size_bytes = os_mod.path.getsize(item_path)
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
    os_mod = _get_os()
    shutil_mod = _get_shutil()
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    try:
        os_mod.makedirs(os_mod.path.dirname(full), exist_ok=True)
        backup_note = ""
        if os_mod.path.exists(full):
            backup = full + ".bak"
            shutil_mod.copy2(full, backup)
            backup_note = f" (previous version backed up to '{os_mod.path.basename(backup)}')"
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        size = os_mod.path.getsize(full)
        return f"File '{file_path}' written successfully ({size} bytes).{backup_note}"
    except Exception as e:
        return f"Error writing file: {e}"

def run_bash(command: str) -> str:
    sub_mod = _get_subprocess()
    from jurbas.security import _SHELL_EXECUTABLE
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
            result = sub_mod.run([_SHELL_EXECUTABLE, "-c", command], shell=False, **kwargs)
        else:
            result = sub_mod.run(command, shell=True, **kwargs)
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
        from jurbas.security import _IS_WINDOWS
        shell_name = "cmd.exe" if _IS_WINDOWS else (_SHELL_EXECUTABLE or "shell")
        return f"Error: shell ({shell_name}) not found."
    except sub_mod.TimeoutExpired:
        return f"Error: command timed out after {BASH_TIMEOUT}s."
    except PermissionError:
        return "Error: permission denied while running command."
    except Exception as e:
        return f"Error executing command: {e}"

def web_search(query: str, max_results: int = 5) -> str:
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
