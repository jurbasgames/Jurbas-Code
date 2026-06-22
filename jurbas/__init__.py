"""Jurbas-Code — modular terminal agent package."""

from importlib import metadata

try:
    __version__ = metadata.version("jurbas-code")
except metadata.PackageNotFoundError:  # running from source / not installed
    __version__ = "0.1.0"

from .security import (
    ALLOWED_BASE,
    MAX_TOOL_STEPS,
    safe_path,
    is_secret_path,
    load_dotenv,
    _is_dangerous,
    _is_readonly_bash,
    _requires_confirmation,
    confirm_action,
)
from .config import SYSTEM_PROMPT, tools_schema
from .tools import TOOL_HANDLERS, read_file, list_directory, write_file, run_bash, web_search, HAS_WEB_SEARCH

__all__ = [
    "__version__",
    "ALLOWED_BASE",
    "MAX_TOOL_STEPS",
    "safe_path",
    "is_secret_path",
    "load_dotenv",
    "_is_dangerous",
    "_is_readonly_bash",
    "_requires_confirmation",
    "confirm_action",
    "SYSTEM_PROMPT",
    "tools_schema",
    "TOOL_HANDLERS",
    "read_file",
    "list_directory",
    "write_file",
    "run_bash",
    "web_search",
    "HAS_WEB_SEARCH",
]
