import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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

def read_file(file_path: str) -> str:
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
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
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

TOOL_HANDLERS = {
    "read_file": lambda args: read_file(args["file_path"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "write_file": lambda args: write_file(args["file_path"], args["content"]),
    "run_bash": lambda args: run_bash(args["command"]),
}

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

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a text file.",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "File path (e.g.: './main.py')."}},
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
                "properties": {"dir_path": {"type": "string", "description": "Directory path (e.g.: './' for project root)."}},
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
                    "file_path": {"type": "string", "description": "Path of the file to be written."},
                    "content": {"type": "string", "description": "Complete content to be written to the file."}
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
            "description": f"Execute a bash command inside the project directory. Timeout is {BASH_TIMEOUT}s. Dangerous commands are blocked.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "The bash command to execute."}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]

# ─── Claude Code Auth logic ───
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."
CLAUDE_CODE_USER_AGENT = "claude-cli/2.1.183 (external, cli)"
ANTHROPIC_VERSION = "2023-06-01"
CLAUDE_CODE_BETA_FLAGS = (
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "redact-thinking-2026-02-12",
    "thinking-token-count-2026-05-13",
    "context-management-2025-06-27",
    "prompt-caching-scope-2026-01-05",
    "mid-conversation-system-2026-04-07",
    "advisor-tool-2026-03-01",
    "advanced-tool-use-2025-11-20",
    "effort-2025-11-24",
    "extended-cache-ttl-2025-04-11",
    "cache-diagnosis-2026-04-07",
)

def claude_config_dir():
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".claude"

def load_claude_code_token():
    creds_path = claude_config_dir() / ".credentials.json"
    try:
        data = json.loads(creds_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Aviso: nao foi possivel ler {creds_path}: {exc}", file=sys.stderr)
        return None
    oauth = data.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not token:
        return None
    expires_at = oauth.get("expiresAt")
    if isinstance(expires_at, (int, float)) and expires_at / 1000 < time.time():
        print("Aviso: o token do Claude Code em ~/.claude parece expirado. Rode `claude` para renovar a sessao.", file=sys.stderr)
    return token

def resolve_claude_token():
    return os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or load_claude_code_token()

def claude_code_headers():
    return {
        "User-Agent": CLAUDE_CODE_USER_AGENT,
        "X-Claude-Code-Session-Id": str(uuid.uuid4()),
        "X-Stainless-Arch": "x64",
        "X-Stainless-Lang": "js",
        "X-Stainless-OS": "Linux",
        "X-Stainless-Package-Version": "0.94.0",
        "X-Stainless-Retry-Count": "0",
        "X-Stainless-Runtime": "node",
        "X-Stainless-Runtime-Version": "v24.3.0",
        "X-Stainless-Timeout": "600",
        "anthropic-beta": ",".join(CLAUDE_CODE_BETA_FLAGS),
        "anthropic-dangerous-direct-browser-access": "true",
        "anthropic-version": ANTHROPIC_VERSION,
        "x-app": "cli",
        "x-client-request-id": str(uuid.uuid4()),
    }

def get_claude_client():
    if os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY esta setado; remova para evitar API billing.")
    import anthropic
    token = resolve_claude_token()
    if not token:
        raise RuntimeError("Nao encontrei credenciais do Claude Code.")
    return anthropic.Anthropic(auth_token=token, default_headers=claude_code_headers())

# ─── Converter for Anthropic ───
def convert_to_anthropic_tools(openai_tools):
    anthropic_tools = []
    for t in openai_tools:
        anthropic_tools.append({
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"]
        })
    return anthropic_tools

def convert_messages_to_anthropic(messages):
    anthropic_msgs = []
    for m in messages:
        if m["role"] == "system":
            continue
        elif m["role"] == "user":
            anthropic_msgs.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            content = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            if m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"])
                    })
            if content:
                anthropic_msgs.append({"role": "assistant", "content": content})
        elif m["role"] == "tool":
            last_msg = anthropic_msgs[-1] if anthropic_msgs else None
            block = {
                "type": "tool_result",
                "tool_use_id": m["tool_call_id"],
                "content": m["content"]
            }
            if last_msg and last_msg["role"] == "user" and isinstance(last_msg["content"], list):
                last_msg["content"].append(block)
            else:
                anthropic_msgs.append({"role": "user", "content": [block]})
    return anthropic_msgs

def main():
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()
    
    if provider == "deepseek":
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
    elif provider == "claude":
        client = get_claude_client()
    else:
        sys.exit(f"Provider desconhecido: {provider}. Use 'claude' ou 'deepseek'.")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    session_tokens = {"prompt": 0, "completion": 0, "total": 0}

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        for _step in range(MAX_TOOL_STEPS):
            if provider == "deepseek":
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

                usage = response.usage
                if usage:
                    p_tokens = usage.prompt_tokens or 0
                    c_tokens = usage.completion_tokens or 0
                    t_tokens = usage.total_tokens or 0
                    session_tokens["prompt"] += p_tokens
                    session_tokens["completion"] += c_tokens
                    session_tokens["total"] += t_tokens
                    print(f"  [Tokens] Request: {p_tokens}p / {c_tokens}c ({t_tokens} total) | Session: {session_tokens['prompt']}p / {session_tokens['completion']}c")

                assistant_msg = response.choices[0].message
                messages.append(assistant_msg.model_dump(exclude_none=True))
                
                finish = response.choices[0].finish_reason
                if finish != "tool_calls":
                    reply = (assistant_msg.content or "").strip()
                    print(f"AI: {reply}\n")
                    break
                
                tool_calls = assistant_msg.tool_calls
                
            elif provider == "claude":
                anthropic_messages = convert_messages_to_anthropic(messages)
                system_prompt = next((m["content"] for m in messages if m["role"] == "system"), SYSTEM_PROMPT)
                
                response = client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=16000,
                    system=[
                        {"type": "text", "text": CLAUDE_CODE_IDENTITY},
                        {"type": "text", "text": system_prompt},
                    ],
                    messages=anthropic_messages,
                    tools=convert_to_anthropic_tools(tools),
                )
                
                usage = response.usage
                if usage:
                    p_tokens = usage.input_tokens or 0
                    c_tokens = usage.output_tokens or 0
                    t_tokens = p_tokens + c_tokens
                    session_tokens["prompt"] += p_tokens
                    session_tokens["completion"] += c_tokens
                    session_tokens["total"] += t_tokens
                    print(f"  [Tokens] Request: {p_tokens}p / {c_tokens}c ({t_tokens} total) | Session: {session_tokens['prompt']}p / {session_tokens['completion']}c")
                
                assistant_text = ""
                tool_calls = []
                for block in response.content:
                    if block.type == "text":
                        assistant_text += block.text
                    elif block.type == "tool_use":
                        tool_calls.append({
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.input)
                            }
                        })
                
                assistant_msg = {"role": "assistant", "content": assistant_text}
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)
                
                if not tool_calls:
                    reply = assistant_text.strip()
                    print(f"AI: {reply}\n")
                    break

            for tc in tool_calls:
                name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"]
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    if not isinstance(args, dict):
                        raise ValueError("tool arguments must be a JSON object")
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"  🔧 [{name}] (failed to parse args: {raw_args})")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
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
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": result,
                })
        else:
            print(f"AI: stopped after reaching the max of {MAX_TOOL_STEPS} tool steps.\n")

if __name__ == '__main__':
    main()
