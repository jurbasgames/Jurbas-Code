"""Security configuration: path validation, secret detection, and .env loading."""

import os
import platform
import re
import shutil
import subprocess

# ─── Allowed base directory (anchored relative to this file's parent) ───
ALLOWED_BASE = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))

_IS_WINDOWS = platform.system() == "Windows"


def _bash_is_usable(bash_path: str) -> bool:
    """Return False if bash_path is the WSL stub with no distro installed.

    On Windows, ``shutil.which("bash")`` may resolve to the WSL launcher
    (``C:\\Windows\\System32\\bash.exe``).  When no WSL distro is installed
    that stub exits with a non-zero code and prints the 'no distributions'
    error — before the real command ever runs.  We probe it with
    ``bash --version`` (timeout 3 s) and treat any non-zero exit as unusable.

    On non-Windows platforms, or when ``WSL_DISTRO_NAME`` is already set
    (meaning we *are* inside WSL), always return True to skip the probe.
    """
    if not _IS_WINDOWS:
        return True
    if os.environ.get("WSL_DISTRO_NAME"):
        # We are running inside WSL — bash is definitely usable.
        return True
    try:
        r = subprocess.run(
            [bash_path, "--version"],
            capture_output=True,
            timeout=3,
            stdin=subprocess.DEVNULL,
        )
        return r.returncode == 0
    except Exception:
        return False


def _resolve_shell() -> tuple[str | None, bool]:
    """Return (executable_path_or_None, use_shell_bool) for subprocess.

    On Windows: first try to locate a *usable* bash.exe (Git Bash / working
    WSL), then fall back to cmd.exe via shell=True (executable=None).
    On Unix: prefer /bin/bash, fall back to /bin/sh, then shell=True fallback.
    Returns (executable, shell) tuple.
    """
    if _IS_WINDOWS:
        # Prefer bash if available and usable (Git Bash, working WSL, etc.)
        bash_path = shutil.which("bash")
        if bash_path and _bash_is_usable(bash_path):
            return bash_path, True
        for path in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if os.path.isfile(path) and _bash_is_usable(path):
                return path, True
        return None, True  # cmd.exe is resolved automatically by Windows
    for candidate in ("/bin/bash", "/usr/bin/bash", "/bin/sh", "/usr/bin/sh"):
        if os.path.isfile(candidate):
            return candidate, True
    return None, True  # last-resort: let the OS pick


_SHELL_EXECUTABLE, _SHELL_USE_SHELL = _resolve_shell()

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
    On Windows, normcase is applied so the comparison is case-insensitive.
    """
    path = file_path or "."
    if os.path.isabs(path):
        full = os.path.realpath(path)
    else:
        full = os.path.realpath(os.path.join(ALLOWED_BASE, path))
    try:
        allowed_norm = os.path.normcase(ALLOWED_BASE)
        full_norm = os.path.normcase(full)
        if os.path.commonpath([allowed_norm, full_norm]) != allowed_norm:
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
    # Unix-style
    "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf .",
    "mkfs", "dd if=", "fdisk",
    ":(){ :|:& };:",
    "chmod 000", "chown -R",
    "> /dev/sda", "> /dev/sdb",
    "wget ", "curl ",
    "sudo ", "su ",
    # Windows-style
    "del /f /s /q c:\\", "del /f /s /q c:/",
    "format c:", "format c:/",
    "rd /s /q c:\\", "rd /s /q c:/",
    "rmdir /s /q c:\\", "rmdir /s /q c:/",
    "cipher /w:c", "sfc /scannow",
    "reg delete",
    "net user", "net localgroup",
    "shutdown /", "taskkill /f",
]

# On Windows 'format' is a built-in cmd command — keep the Windows-specific entry above
# but exclude the bare Unix 'format' string to avoid false positives on Windows paths.
if not _IS_WINDOWS:
    DANGEROUS_PATTERNS.append("format")


def _is_dangerous(command: str) -> str | None:
    """Check if a command contains blacklisted patterns. Returns a reason or None."""
    lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lower:
            return f"Command blocked for security reasons (matches dangerous pattern: '{pattern}')"
    # Block piping to any shell — covers Unix (sh/bash) and Windows (cmd/powershell/pwsh)
    if re.search(r'\|\s*(sudo\s+)?([^|\s]*[\\/])?(sh|bash|cmd|powershell|pwsh)\b', lower):
        return "Piping to a shell interpreter is blocked for security."
    return None


# ─── Readonly / mutation detection for Bash tool ───
READONLY_BASH = {
    "ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "tree",
    "stat", "file", "which", "whoami", "date", "echo", "env", "du", "df", "uname",
}
# Windows equivalents for read-only detection
READONLY_CMD = {
    "dir", "type", "echo", "date", "time", "ver", "whoami",
    "where", "tree", "set", "path", "hostname",
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
    head = tokens[0].lower()
    if head == "git":
        sub = tokens[1] if len(tokens) > 1 else ""
        return sub in READONLY_GIT_SUBCMDS
    # Use READONLY_BASH when a bash-compatible shell is active (even on Windows),
    # fall back to READONLY_CMD only when running plain cmd.exe.
    is_bash = not _IS_WINDOWS or (
        _SHELL_EXECUTABLE is not None and "bash" in _SHELL_EXECUTABLE.lower())
    readonly_set = READONLY_BASH if is_bash else READONLY_CMD
    return head in readonly_set


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
        print(
            f"      write_file: {args.get('file_path', '')} ({len(content)} chars)")
    else:
        print(f"      {name}: {args}")
    try:
        answer = input("  Approve? [Y/n] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes", "")
