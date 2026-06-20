import json
import os
import re
import shutil
import subprocess
from openai import OpenAI

# ─── Security configuration ───
ALLOWED_BASE = os.path.realpath("./")
MAX_TOOL_STEPS = 25  # safety cap on consecutive tool-call iterations
BASH_TIMEOUT = 60*5

# Commands/patterns that are never allowed (blocked by prefix match)
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
    # Block pipe-to-dangerous destinations
    if re.search(r'\|\s*(sudo\s+)?([^|\s]*/)?(sh|bash)\b', lower):
        return "Piping to sudo/sh/bash is blocked for security."
    return None


# ─── Confirmation gate ───
# Commands considered read-only and safe to auto-run without asking the user.
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
    if not cmd or any(op in cmd for op in SHELL_OPERATORS):
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
        print(
            f"      write_file: {args.get('file_path', '')} ({len(content)} chars)")
    else:
        print(f"      {name}: {args}")
    try:
        answer = input("  Approve? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")


# ─── Tools ───

def read_file(file_path: str) -> str:
    """Read file content with security checks."""
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
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
    """Execute a bash command inside the project directory and return its output.

    Use this for git operations, running scripts, installing dependencies,
    or any shell-level task. The command runs in './' (ALLOWED_BASE) as working
    directory with a {BASH_TIMEOUT}s timeout.

    Dangerous commands (rm -rf /, sudo, mkfs, etc.) are blocked for safety.
    """
    if not isinstance(command, str):
        return "Error: command must be a string."

    # Security check
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


# ─── Tool mapping ───
TOOL_HANDLERS = {
    "read_file": lambda args: read_file(args["file_path"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "write_file": lambda args: write_file(args["file_path"], args["content"]),
    "run_bash": lambda args: run_bash(args["command"]),
}

# ─── System Prompt ───
SYSTEM_PROMPT = (
    "You are a terminal agent with SELF-MODIFICATION capability. You can read, list, WRITE files, and execute BASH commands — including your own source code (main.py). Your purpose is to evolve your own capabilities: when the user asks for a new feature, read your current code, generate a modified version, and overwrite the corresponding file.\n\n"
    "Rules:\n"
    "- Always read main.py before modifying it to understand the current state.\n"
    "- Think carefully before writing: the code must compile and run.\n"
    "- Maintain the existing style and structure when adding tools.\n"
    "- When finished with a modification, explain what was changed.\n"
    "- Always respond in English.\n"
    "- Use list_directory to explore the project structure.\n"
    "- Use run_bash for any shell task: git, pip, python, ls, etc.\n"
    "- Prefer run_bash for git operations (git status, git add, git commit, git log).\n"
    "- Mutating actions (file writes, git commit/push, rm, installs) require user approval; if one is declined, adapt instead of retrying it."
)

# ─── Tool definitions (OpenAI schema) ───
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path (e.g.: './main.py')."
                    }
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Directory path (e.g.: './' for project root)."
                    }
                },
                "required": ["dir_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a file. Creates parent directories if needed. Use to modify your own code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path of the file to be written (e.g.: './main.py')."
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete content to be written to the file."
                    }
                },
                "required": ["file_path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": (
                "Execute a bash command inside the project directory. "
                "Use for git operations, running scripts, listing files, installing packages, etc. "
                f"Timeout is {BASH_TIMEOUT}s. Dangerous commands are blocked."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute (e.g.: 'git status', 'ls -la', 'python script.py')."
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]


def main():
    # ─── DeepSeek Client ───
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    # ─── Initial history ───
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # ─── Main loop ───
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # ── Tool call loop (allows multiple steps, bounded for safety) ──
        for _step in range(MAX_TOOL_STEPS):
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=messages,
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
                tools=tools,
                tool_choice="auto",
            )

            if not response.choices:
                print("AI: Error: No response choices returned from the API.\n")
                break

            assistant_msg = response.choices[0].message
            # Store as a plain dict so the history stays JSON-serializable.
            messages.append(assistant_msg.model_dump(exclude_none=True))

            finish = response.choices[0].finish_reason

            if finish != "tool_calls":
                reply = (assistant_msg.content or "").strip()
                print(f"AI: {reply}\n")
                break

            for tool_call in assistant_msg.tool_calls:
                name = tool_call.function.name
                raw_args = tool_call.function.arguments
                try:
                    args = json.loads(raw_args) if isinstance(
                        raw_args, str) else raw_args
                    if not isinstance(args, dict):
                        raise ValueError("tool arguments must be a JSON object")
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"  🔧 [{name}] (failed to parse args: {raw_args})")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": f"Error: invalid JSON arguments: {e}",
                    })
                    continue
                print(f"  🔧 [{name}] {args}")

                handler = TOOL_HANDLERS.get(name)
                if handler is None:
                    result = f"Error: unknown tool '{name}'."
                elif _requires_confirmation(name, args) and not confirm_action(name, args):
                    print("  ⛔ Declined.\n")
                    result = "Action declined by the user. Do not retry unless explicitly asked."
                else:
                    try:
                        result = handler(args)
                    except KeyError as e:
                        result = f"Error: missing required argument {e} for tool '{name}'."
                    except Exception as e:
                        result = f"Error executing '{name}': {e}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result,
                })
        else:
            # Loop exhausted without a final (non-tool) response.
            print(
                f"AI: stopped after reaching the max of {MAX_TOOL_STEPS} tool steps.\n")


if __name__ == '__main__':
    main()
