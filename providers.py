import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, cast

from openai import OpenAI

DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
CLAUDE_MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "4096"))
CLAUDE_THINKING_BUDGET_TOKENS = int(os.environ.get("CLAUDE_THINKING_BUDGET_TOKENS", "1024"))
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."
CLAUDE_CODE_USER_AGENT = "claude-cli/2.1.183 (external, cli)"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
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


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not configured. Set it in the environment or .env.")
    return value


def claude_config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override).expanduser() if override else Path.home() / ".claude"


def load_claude_code_token() -> str | None:
    creds_path = claude_config_dir() / ".credentials.json"
    try:
        data = json.loads(creds_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read {creds_path}: {exc}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        return None
    oauth = data.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        return None
    token = oauth.get("accessToken")
    if not isinstance(token, str) or not token:
        return None

    expires_at = oauth.get("expiresAt")
    if isinstance(expires_at, (int, float)) and expires_at / 1000 < time.time():
        print("Warning: Claude Code OAuth token appears expired. Run `claude` to renew it.", file=sys.stderr)
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


def anthropic_tools(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool["function"]["name"],
            "description": tool["function"].get("description", ""),
            "input_schema": tool["function"].get("parameters", {"type": "object"}),
        }
        for tool in openai_tools
    ]


def anthropic_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    converted = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            continue
        if role == "tool":
            converted.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": message["tool_call_id"],
                    "content": message.get("content", ""),
                }],
            })
        elif role == "assistant":
            blocks = []
            if message.get("content"):
                blocks.append({"type": "text", "text": message["content"]})
            for tool_call in message.get("tool_calls") or []:
                raw_args = tool_call.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {"_invalid_json": raw_args}
                blocks.append({
                    "type": "tool_use",
                    "id": tool_call["id"],
                    "name": tool_call["function"]["name"],
                    "input": args,
                })
            if blocks:
                converted.append({"role": "assistant", "content": blocks})
        else:
            converted.append({"role": "user", "content": message.get("content", "")})
    return "\n\n".join(system_parts), converted


def post_claude_message(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {
        **claude_code_headers(),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        ANTHROPIC_MESSAGES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Claude request failed ({exc.code}): {body}") from exc


def openai_style_from_anthropic(message: dict[str, Any]) -> tuple[dict[str, Any], str]:
    content_parts = []
    tool_calls = []
    for block in message.get("content", []):
        if block.get("type") == "text":
            content_parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block["id"],
                "type": "function",
                "function": {
                    "name": block["name"],
                    "arguments": json.dumps(block.get("input") or {}),
                },
            })
    assistant: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts)}
    if tool_calls:
        assistant["tool_calls"] = tool_calls
    return assistant, "tool_calls" if tool_calls else (message.get("stop_reason") or "stop")


def completion_runner(openai_tools: list[dict[str, Any]]):
    provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    if provider == "deepseek":
        client = OpenAI(api_key=require_env("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

        def complete(messages: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=cast(Any, messages),
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
                tools=cast(Any, openai_tools),
                tool_choice="auto",
            )
            if not response.choices:
                return None, None
            return response.choices[0].message.model_dump(exclude_none=True), response.choices[0].finish_reason

        return complete

    if provider == "claude":
        if os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is set; unset it to avoid Anthropic API billing. "
                "The Claude provider uses Claude Code OAuth credentials."
            )
        token = resolve_claude_token()
        if not token:
            raise RuntimeError(
                "Claude Code credentials not found. Run `claude` to create ~/.claude/.credentials.json "
                "or set CLAUDE_CODE_OAUTH_TOKEN."
            )
        claude_tools = anthropic_tools(openai_tools)

        def complete(messages: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
            system, claude_messages = anthropic_messages(messages)
            payload: dict[str, Any] = {
                "model": CLAUDE_MODEL,
                "max_tokens": CLAUDE_MAX_TOKENS,
                "system": f"{CLAUDE_CODE_IDENTITY}\n\n{system}",
                "messages": claude_messages,
                "tools": claude_tools,
            }
            if 0 < CLAUDE_THINKING_BUDGET_TOKENS < CLAUDE_MAX_TOKENS:
                payload["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": CLAUDE_THINKING_BUDGET_TOKENS,
                }
            return openai_style_from_anthropic(post_claude_message(token, payload))

        return complete

    raise RuntimeError("Unknown LLM_PROVIDER: %r. Use 'deepseek' or 'claude'." % provider)
