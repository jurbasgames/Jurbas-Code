import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

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

def claude_config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".claude"

def load_claude_code_token() -> str | None:
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

def resolve_claude_token() -> str | None:
    return os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or load_claude_code_token()

def claude_code_headers() -> dict[str, str]:
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

def get_claude_client() -> Any:
    if os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY esta setado; remova para evitar API billing.")
    import anthropic
    token = resolve_claude_token()
    if not token:
        raise RuntimeError("Nao encontrei credenciais do Claude Code.")
    return anthropic.Anthropic(auth_token=token, default_headers=claude_code_headers())

def get_client(provider_name: str) -> Any:
    provider = provider_name.lower()
    if provider == "deepseek":
        from openai import OpenAI
        return OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
    elif provider == "claude":
        return get_claude_client()
    else:
        raise ValueError(f"Provider desconhecido: {provider}. Use 'claude' ou 'deepseek'.")

# ─── Converters ───
def convert_to_anthropic_tools(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anthropic_tools = []
    for t in openai_tools:
        function = t.get("function", {})
        anthropic_tools.append({
            "name": function.get("name"),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
        })
    return anthropic_tools


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def convert_messages_to_anthropic(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                    function = tc.get("function", {})
                    content.append({
                        "type": "tool_use",
                        "id": tc.get("id"),
                        "name": function.get("name"),
                        "input": _parse_tool_arguments(function.get("arguments")),
                    })
            if content:
                anthropic_msgs.append({"role": "assistant", "content": content})
        elif m["role"] == "tool":
            last_msg = anthropic_msgs[-1] if anthropic_msgs else None
            block = {
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id"),
                "content": m.get("content"),
            }
            if last_msg and last_msg["role"] == "user":
                if isinstance(last_msg["content"], str):
                    last_msg["content"] = [{"type": "text", "text": last_msg["content"]}]
                last_msg["content"].append(block)
            else:
                anthropic_msgs.append({"role": "user", "content": [block]})
    return anthropic_msgs

def normalize_tool_call(tool_call: Any) -> dict[str, Any]:
    """Return a plain dict for tool calls from either OpenAI/DeepSeek or Anthropic."""
    if isinstance(tool_call, dict):
        return tool_call
    function = getattr(tool_call, "function", None)
    function_is_dict = isinstance(function, dict)
    return {
        "id": getattr(tool_call, "id", None),
        "type": getattr(tool_call, "type", "function"),
        "function": {
            "name": function.get("name") if function_is_dict else getattr(function, "name", None),
            "arguments": function.get("arguments", "{}") if function_is_dict else getattr(function, "arguments", "{}"),
        },
    }
