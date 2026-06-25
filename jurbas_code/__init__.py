"""Jurbas-Code — terminal agent package (single canonical package)."""

from importlib import import_module, metadata
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


_LAZY_EXPORTS = {
    "ALLOWED_BASE": ("jurbas_code.security", "ALLOWED_BASE"),
    "MAX_TOOL_STEPS": ("jurbas_code.security", "MAX_TOOL_STEPS"),
    "safe_path": ("jurbas_code.security", "safe_path"),
    "is_secret_path": ("jurbas_code.security", "is_secret_path"),
    "load_dotenv": ("jurbas_code.security", "load_dotenv"),
    "_is_dangerous": ("jurbas_code.security", "_is_dangerous"),
    "_is_readonly_bash": ("jurbas_code.security", "_is_readonly_bash"),
    "_requires_confirmation": ("jurbas_code.security", "_requires_confirmation"),
    "confirm_action": ("jurbas_code.security", "confirm_action"),
    "SYSTEM_PROMPT": ("jurbas_code.prompts", "SYSTEM_PROMPT"),
    "tools_schema": ("jurbas_code.tool_schemas", "tools"),
    "Config": ("jurbas_code.config", "Config"),
    "TOOL_HANDLERS": ("jurbas_code.tools", "TOOL_HANDLERS"),
    "read_file": ("jurbas_code.tools", "read_file"),
    "list_directory": ("jurbas_code.tools", "list_directory"),
    "write_file": ("jurbas_code.tools", "write_file"),
    "run_bash": ("jurbas_code.tools", "run_bash"),
    "web_search": ("jurbas_code.tools", "web_search"),
    "HAS_WEB_SEARCH": ("jurbas_code.tools", "HAS_WEB_SEARCH"),
}


def __getattr__(name: str):
    """Lazily expose compatibility facade symbols without import side effects."""
    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = ["__version__", *_LAZY_EXPORTS]
