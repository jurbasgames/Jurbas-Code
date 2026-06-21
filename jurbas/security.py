"""Security configuration: path validation, secret detection, and .env loading."""

import os
import re

# ─── Allowed base directory (anchored relative to this file's parent) ───
ALLOWED_BASE = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))

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


# ─── Dangerous command checks ───
DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf .",
    "mkfs", "dd if=", "format", "fdisk",
    ":(){ :|:& };:",
    "chmod 000", "chown -R",
    "> /dev/sda", "> /dev/sdb",
    "wget ", "curl ",
    "sudo ", "su ",
]

def _is_dangerous(command: str) -> str | None:
    """Check if a command contains blacklisted patterns. Returns a reason or None."""
    lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lower:
            return f"Command blocked for security reasons (matches dangerous pattern: '{pattern}')"
    if re.search(r'\|\s*(sudo\s+)?([^|\s]*/)?(sh|bash)\b', lower):
        return "Piping to sudo/sh/bash is blocked for security."
    return None


# ─── Readonly / mutation detection for Bash tool ───
READONLY_BASH = {
    "ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "tree",
    "stat", "file", "which", "whoami", "date", "echo", "du", "df", "uname",
}
READONLY_GIT_SUBCMDS = {
    "status", "log", "diff", "show",
    "ls-files", "rev-parse", "blame", "describe",
}
SHELL_OPERATORS = ("&&", "||", ";", "|", ">", "<", "`", "$(", "&")
MUTATING_FLAGS = {"-d", "-D", "--delete", "-f", "--force", "--prune", "--hard"}


def _is_readonly_bash(command: str) -> bool:
    """Best-effort check: True only for commands that clearly cannot mutate state.

    Conservative by design — anything ambiguous (shell operators, mutating flags,
    unknown commands) returns False so it gets gated behind a confirmation prompt
    instead of running unattended.
    """
    if not isinstance(command, str):
        return False
    cmd = command.strip()
    if not cmd or any(op in cmd for op in SHELL_OPERATORS) or "\n" in cmd or "\r" in cmd:
        return False
    tokens = cmd.split()
    if any(t in MUTATING_FLAGS for t in tokens):
        return False
    head = tokens[0]
    if head == "git":
        sub = tokens[1] if len(tokens) > 1 else ""
        return sub in READONLY_GIT_SUBCMDS
    return head in READONLY_BASH


def _requires_confirmation(name: str, args) -> bool:
    """Decide whether a tool call needs explicit user approval before running."""
    if not isinstance(args, dict):
        return True
    if name == "write_file":
        return True
    if name == "run_bash":
        command = args.get("command", "")
        return not _is_readonly_bash(command)
    return False


def confirm_action(name: str, args) -> bool:
    """Prompt the user to approve a mutating action. Returns True if approved."""
    args = args if isinstance(args, dict) else {}
    print("\n  ⚠️  The agent wants to perform a mutating action:")
    if name == "run_bash":
        print(f"      $ {args.get('command', '')}")
    elif name == "write_file":
        content = args.get("content", "")
        print(f"      write_file: {args.get('file_path', '')} ({len(content)} chars)")
    else:
        print(f"      {name}: {args}")
    try:
        answer = input("  Approve? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")
