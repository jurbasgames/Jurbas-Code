"""Jurbas-Code — terminal agent with SELF-MODIFICATION capability.

Usage:
    python main.py          # Run interactive REPL
    python main.py --serve  # Same (kept for compatibility)
"""

import json
import os
import sys
import uuid
import time
from pathlib import Path

# Re-export all public symbols so that ``import main`` and
# ``from main import safe_path`` continue to work (backwards compat).
from jurbas import (           # noqa: F401
    ALLOWED_BASE,
    MAX_TOOL_STEPS,
    safe_path,
    is_secret_path,
    load_dotenv,
    _is_dangerous,
    _is_readonly_bash,
    _requires_confirmation,
    confirm_action,
    SYSTEM_PROMPT,
    tools,
    TOOL_HANDLERS,
    read_file,
    list_directory,
    write_file,
    run_bash,
)
from jurbas.git_utils import extract_git_info, analyze_pr  # noqa: F401

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

def normalize_tool_call(tool_call):
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

# ─── Auto-extract on module load ───
_extracted = False
if os.path.exists(os.path.join(ALLOWED_BASE, ".git")):
    try:
        extract_git_info()
        _extracted = True
    except Exception as e:
        print(f"⚠️ Auto-extract error: {e}")

def main():
    load_dotenv()
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()
    
    if provider == "deepseek":
        api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not api_key:
            print("Error: DEEPSEEK_API_KEY environment variable is not set or is empty.")
            sys.exit(1)
        from openai import OpenAI, AuthenticationError, APIError, RateLimitError, APITimeoutError
        client = OpenAI(
            api_key=api_key,
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
                try:
                    response_stream = client.chat.completions.create(
                        model="deepseek-v4-flash",
                        messages=messages,
                        stream=True,
                        reasoning_effort="high",
                        extra_body={"thinking": {"type": "enabled"}},
                        tools=tools,
                        tool_choice="auto",
                        stream_options={"include_usage": True},
                    )
                except AuthenticationError as e:
                    print(f"AI: Authentication Error: The API key starting with '{api_key[:4]}' is invalid or expired. {e}")
                    sys.exit(1)
                except RateLimitError as e:
                    print(f"AI: Rate Limit Error: {e}\n")
                    break
                except APITimeoutError as e:
                    print(f"AI: Timeout Error: {e}\n")
                    break
                except APIError as e:
                    print(f"AI: API Error: {e}")
                    # Drop the failed turn
                    while messages and messages[-1].get("role") != "user":
                        messages.pop()
                    if messages and messages[-1].get("role") == "user":
                        messages.pop()
                    break
                except Exception as e:
                    print(f"AI: Unexpected Error: {e}")
                    break

                role = "assistant"
                content = ""
                content_seen = False
                reasoning_content = ""
                tool_calls = []
                printed_ai_prefix = False

                try:
                    for chunk in response_stream:
                        if not chunk.choices:
                            usage = getattr(chunk, "usage", None)
                            if usage:
                                p_tokens = usage.prompt_tokens or 0
                                c_tokens = usage.completion_tokens or 0
                                t_tokens = usage.total_tokens or 0
                                session_tokens["prompt"] += p_tokens
                                session_tokens["completion"] += c_tokens
                                session_tokens["total"] += t_tokens
                                print(f"  [Tokens] Request: {p_tokens}p / {c_tokens}c ({t_tokens} total) | Session: {session_tokens['prompt']}p / {session_tokens['completion']}c ({session_tokens['total']} total)")
                            continue
                        delta = chunk.choices[0].delta
                        if getattr(delta, "role", None):
                            role = delta.role
                        reasoning = getattr(delta, "reasoning_content", None)
                        if reasoning:
                            if not printed_ai_prefix:
                                print("AI: ", end="", flush=True)
                                printed_ai_prefix = True
                            reasoning_content += reasoning
                            print(reasoning, end="", flush=True)

                        if getattr(delta, "content", None) is not None:
                            content_seen = True
                            content += delta.content
                            if delta.content:
                                if not printed_ai_prefix:
                                    print("AI: ", end="", flush=True)
                                    printed_ai_prefix = True
                                print(delta.content, end="", flush=True)

                        tool_calls_chunk = getattr(delta, "tool_calls", None)
                        if tool_calls_chunk:
                            for tc_chunk in tool_calls_chunk:
                                index = tc_chunk.index
                                while len(tool_calls) <= index:
                                    tool_calls.append({
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    })
                                if tc_chunk.id:
                                    tool_calls[index]["id"] += tc_chunk.id
                                if getattr(tc_chunk, "type", None):
                                    tool_calls[index]["type"] = tc_chunk.type
                                if getattr(tc_chunk.function, "name", None):
                                    tool_calls[index]["function"]["name"] += tc_chunk.function.name
                                if getattr(tc_chunk.function, "arguments", None):
                                    tool_calls[index]["function"]["arguments"] += tc_chunk.function.arguments
                except Exception as e:
                    print(f"\n[Stream interrupted: {e}]")
                    break

                if printed_ai_prefix:
                    print()

                if not content_seen and not content and not reasoning_content and not tool_calls:
                    print("AI: Error: No response choices returned from the API.\n")
                    break

                assistant_msg_dict = {"role": role}
                if content_seen or content or tool_calls:
                    assistant_msg_dict["content"] = content
                if reasoning_content:
                    assistant_msg_dict["reasoning_content"] = reasoning_content
                if tool_calls:
                    assistant_msg_dict["tool_calls"] = [normalize_tool_call(tc) for tc in tool_calls]
                    tool_calls = assistant_msg_dict["tool_calls"]

                messages.append(assistant_msg_dict)

                if not tool_calls:
                    break

            elif provider == "claude":
                anthropic_messages = convert_messages_to_anthropic(messages)
                system_prompt = next((m["content"] for m in messages if m["role"] == "system"), SYSTEM_PROMPT)
                
                try:
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
                except Exception as e:
                    print(f"AI: Unexpected Error: {e}")
                    break

                usage = response.usage
                if usage:
                    p_tokens = usage.input_tokens or 0
                    c_tokens = usage.output_tokens or 0
                    t_tokens = p_tokens + c_tokens
                    session_tokens["prompt"] += p_tokens
                    session_tokens["completion"] += c_tokens
                    session_tokens["total"] += t_tokens
                    print(f"  [Tokens] Request: {p_tokens}p / {c_tokens}c ({t_tokens} total) | Session: {session_tokens['prompt']}p / {session_tokens['completion']}c ({session_tokens['total']} total)")
                
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

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        main()
    else:
        if not _extracted:
            try:
                analyze_pr()
            except Exception as e:
                print(f"⚠️  analyze_pr error: {e}")
        main()
