"""Jurbas-Code — modular terminal agent package."""

from importlib import metadata
from pathlib import Path
import tomllib


def _read_version_from_pyproject() -> str:
    """Read the source checkout version from pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        version = pyproject["project"]["version"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        return "0.0.0"
    return version if isinstance(version, str) and version else "0.0.0"


try:
    __version__ = metadata.version("jurbas-code")
except metadata.PackageNotFoundError:  # running from source / not installed
    __version__ = _read_version_from_pyproject()

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
