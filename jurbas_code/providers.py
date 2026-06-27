import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, TypedDict, NotRequired, Literal, Union

class ToolFunction(TypedDict):
    name: str
    arguments: str

class ToolCall(TypedDict):
    id: str
    type: Literal["function"]
    function: ToolFunction

class Message(TypedDict):
    role: str
    content: NotRequired[Union[str, list[dict[str, Any]]]]
    tool_calls: NotRequired[list[ToolCall]]
    tool_call_id: NotRequired[str]
    name: NotRequired[str]
    reasoning_content: NotRequired[str]

class AnthropicTool(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]

class AnthropicTextContent(TypedDict):
    type: Literal["text"]
    text: str

class AnthropicToolUseContent(TypedDict):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]

class AnthropicToolResultContent(TypedDict):
    type: Literal["tool_result"]
    tool_use_id: str
    content: str | None

AnthropicContentBlock = Union[AnthropicTextContent, AnthropicToolUseContent, AnthropicToolResultContent]

class AnthropicMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str | list[AnthropicContentBlock]

# ─── Claude Code Auth logic ───
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."
CLAUDE_CODE_USER_AGENT = "claude-cli/2.1.183 (external, cli)"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
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
        print(f"Warning: could not read {creds_path}: {exc}", file=sys.stderr)
        return None
    oauth = data.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not isinstance(token, str):
        return None
    expires_at = oauth.get("expiresAt")
    if isinstance(expires_at, (int, float)) and expires_at / 1000 < time.time():
        print("Warning: Claude Code token in ~/.claude appears expired. Run `claude` to renew the session.", file=sys.stderr)
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
    import anthropic  # type: ignore[import-not-found]
    token = resolve_claude_token()
    if not token:
        raise RuntimeError("Nao encontrei credenciais do Claude Code.")
    return anthropic.Anthropic(auth_token=token, default_headers=claude_code_headers())

def get_client(provider_name: str) -> Any:
    provider = provider_name.lower()
    if provider == "deepseek":
        from openai import OpenAI  # type: ignore[import-not-found]
        return OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
    elif provider == "claude":
        return get_claude_client()
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'claude' or 'deepseek'.")

def _listed_model_ids(client: Any) -> list[str]:
    models = getattr(client, "models", None)
    list_models = getattr(models, "list", None)
    if not callable(list_models):
        return []
    response = list_models()
    items = getattr(response, "data", response)
    model_ids = []
    for item in items:
        model_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        if isinstance(model_id, str) and model_id:
            model_ids.append(model_id)
    return model_ids

def _env_model(provider: str) -> str | None:
    env_var = {
        "claude": "CLAUDE_MODEL",
        "deepseek": "DEEPSEEK_MODEL",
    }.get(provider)
    if env_var:
        model = os.environ.get(env_var, "").strip()
        if model:
            return model
    model = os.environ.get("LLM_MODEL", "").strip()
    return model or None

def resolve_provider_model(provider_name: str, client: Any) -> str:
    provider = provider_name.lower()
    env_model = _env_model(provider)
    if env_model:
        return env_model

    defaults = {
        "claude": DEFAULT_CLAUDE_MODEL,
        "deepseek": DEFAULT_DEEPSEEK_MODEL,
    }
    default_model = defaults.get(provider, DEFAULT_DEEPSEEK_MODEL)
    try:
        model_ids = _listed_model_ids(client)
    except Exception:
        return default_model
    if default_model in model_ids:
        return default_model
    return model_ids[0] if model_ids else default_model

# ─── Converters ───
def convert_to_anthropic_tools(openai_tools: list[dict[str, Any]]) -> list[AnthropicTool]:
    anthropic_tools: list[AnthropicTool] = []
    for t in openai_tools:
        function = t.get("function", {})
        anthropic_tools.append({
            "name": function.get("name", ""),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
        })
    return anthropic_tools


def _parse_tool_arguments(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except (TypeError, json.JSONDecodeError):
        return {}


def convert_messages_to_anthropic(messages: list[Message]) -> list[AnthropicMessage]:
    anthropic_msgs: list[AnthropicMessage] = []
    for m in messages:
        if m["role"] == "system":
            continue
        elif m["role"] == "user":
            content = m.get("content", "")
            if isinstance(content, (str, list)):
                anthropic_msgs.append({"role": "user", "content": content})  # type: ignore[typeddict-item]
        elif m["role"] == "assistant":
            content_blocks: list[AnthropicContentBlock] = []
            m_content = m.get("content")
            if isinstance(m_content, str) and m_content:
                content_blocks.append({"type": "text", "text": m_content})
            if m.get("tool_calls"):
                for tc in m.get("tool_calls", []):
                    function = tc.get("function", {})
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": function.get("name", ""),
                        "input": _parse_tool_arguments(function.get("arguments")),
                    })
            if content_blocks:
                anthropic_msgs.append({"role": "assistant", "content": content_blocks})
        elif m["role"] == "tool":
            last_msg = anthropic_msgs[-1] if anthropic_msgs else None
            m_content = m.get("content")
            block: AnthropicToolResultContent = {
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", ""),
                "content": m_content if isinstance(m_content, str) else json.dumps(m_content),
            }
            if last_msg and last_msg["role"] == "user":
                if isinstance(last_msg["content"], str):
                    last_msg["content"] = [{"type": "text", "text": last_msg["content"]}]
                if isinstance(last_msg["content"], list):
                    last_msg["content"].append(block)
            else:
                anthropic_msgs.append({"role": "user", "content": [block]})
    return anthropic_msgs

def normalize_tool_call(tool_call: Any) -> ToolCall:
    """Return a plain dict for tool calls from either OpenAI/DeepSeek or Anthropic."""
    if isinstance(tool_call, dict):
        tc_id = tool_call.get("id", "")
        tc_type = tool_call.get("type", "function")
        tc_func = tool_call.get("function") or {}
        return {
            "id": tc_id if isinstance(tc_id, str) else "",
            "type": "function",
            "function": {
                "name": tc_func.get("name", "") if isinstance(tc_func, dict) else "",
                "arguments": tc_func.get("arguments", "{}") if isinstance(tc_func, dict) else "{}",
            },
        }
    function = getattr(tool_call, "function", None)
    function_is_dict = isinstance(function, dict)
    tc_id = getattr(tool_call, "id", "")
    tc_name = ""
    tc_args = "{}"
    if isinstance(function, dict):
        tc_name = function.get("name", "")
        tc_args = function.get("arguments", "{}")
    elif function is not None:
        tc_name = getattr(function, "name", "")
        tc_args = getattr(function, "arguments", "{}")

    return {
        "id": tc_id if isinstance(tc_id, str) else "",
        "type": "function",
        "function": {
            "name": tc_name if isinstance(tc_name, str) else "",
            "arguments": tc_args if isinstance(tc_args, str) else "{}",
        },
    }
