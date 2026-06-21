"""Security configuration: path validation, secret detection, and .env loading."""

import os

# ─── Allowed base directory ───
ALLOWED_BASE = os.path.realpath("./")

# ─── Safety cap on consecutive tool-call iterations ───
MAX_TOOL_STEPS = 25

# ─── Known secret / credential file names that must never reach the LLM ───
SECRET_FILE_NAMES = (
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
)
SECRET_FILE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def safe_path(file_path: str) -> str:
    """Resolve and validate a path within the allowed directory.

    Uses realpath so that symlinks are resolved before the boundary check,
    preventing a symlink inside the project from pointing outside it.
    Relative paths are resolved from the project root, not from the caller's CWD.
    """
    path = file_path or "."
    if os.path.isabs(path):
        full = os.path.realpath(path)
    else:
        full = os.path.realpath(os.path.join(ALLOWED_BASE, path))
    try:
        if os.path.commonpath([ALLOWED_BASE, full]) != ALLOWED_BASE:
            raise PermissionError(f"Path not allowed: {file_path}")
    except ValueError:
        raise PermissionError(f"Path not allowed: {file_path}")
    return full


def is_secret_path(file_path: str) -> bool:
    """Return ``True`` for local credential files that must never be sent to the LLM."""
    name = os.path.basename(file_path).lower()
    return (
        name.startswith(".env")
        or name in SECRET_FILE_NAMES
        or name.endswith(SECRET_FILE_SUFFIXES)
    )


def load_dotenv(file_path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a project-local .env file without extra deps.

    Existing environment variables **always win** over values from the file.
    """
    try:
        full = safe_path(file_path)
    except PermissionError:
        return
    if not os.path.exists(full) or not os.path.isfile(full):
        return

    with open(full, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
