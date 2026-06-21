import os
import re

# ─── Security configuration ───
ALLOWED_BASE = os.path.realpath("./")
MAX_TOOL_STEPS = 25
BASH_TIMEOUT = 60*5

DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf .",
    "mkfs", "dd if=", "format", "fdisk",
    ":(){ :|:& };:",
    "chmod 000", "chown -R",
    "> /dev/sda", "> /dev/sdb",
    "wget ", "curl ",
    "sudo ", "su ",
]

def safe_path(file_path: str) -> str:
    """Resolves and validates a path within the allowed directory.

    Uses realpath so that symlinks are resolved before the boundary check,
    preventing a symlink inside the project from pointing outside it.
    """
    full = os.path.realpath(file_path)
    if os.path.commonpath([ALLOWED_BASE, full]) != ALLOWED_BASE:
        raise PermissionError(f"Path not allowed: {file_path}")
    return full

def _is_dangerous(command: str) -> str | None:
    """Check if a command contains blacklisted patterns. Returns a reason or None."""
    lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lower:
            return f"Command blocked for security reasons (matches dangerous pattern: '{pattern}')"
    if re.search(r'\|\s*(sudo\s+)?([^|\s]*/)?(sh|bash)\b', lower):
        return "Piping to sudo/sh/bash is blocked for security."
    return None

READONLY_BASH = {
    "ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "tree",
    "stat", "file", "which", "whoami", "date", "echo", "env", "du", "df", "uname",
}
READONLY_GIT_SUBCMDS = {
    "status", "log", "diff", "show", "branch", "remote",
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
