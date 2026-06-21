"""Jurbas-Code — terminal agent with SELF-MODIFICATION capability.

Usage:
    python main.py          # Run interactive REPL
    python main.py --serve  # Same (kept for compatibility)
"""

import argparse
import json
import os
import sys

try:
    from duckduckgo_search import DDGS
    HAS_WEB_SEARCH = True
except ImportError:
    DDGS = None
    HAS_WEB_SEARCH = False

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
    web_search,
    HAS_WEB_SEARCH,
)

from jurbas_code.providers import (
    CLAUDE_CODE_IDENTITY,
    convert_messages_to_anthropic,
    convert_to_anthropic_tools,
    get_client,
    normalize_tool_call,
)

from jurbas.git_utils import extract_git_info, analyze_pr  # noqa: F401
from openai import AuthenticationError, APIError, RateLimitError, APITimeoutError

# ─── Auto-extract on module load ───
_extracted = False
if os.path.exists(os.path.join(ALLOWED_BASE, ".git")):
    try:
        extract_git_info()
        _extracted = True
    except Exception as e:
        print(f"⚠️ Auto-extract error: {e}")

HISTORY_FILE = "history.json"

def load_history() -> list:
    """Loads message history from file, syncing with the current SYSTEM_PROMPT."""
    initial = [{"role": "system", "content": SYSTEM_PROMPT}]
    if not os.path.exists(HISTORY_FILE):
        return initial
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            messages = json.load(f)
        if not isinstance(messages, list) or not messages:
            return initial
        # Sync system prompt if it changed
        if messages[0].get("role") == "system":
            messages[0]["content"] = SYSTEM_PROMPT
        else:
            messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        return messages
    except Exception:
        return initial


def save_history(messages: list):
    """Saves the current message history to a file."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

def main(args=None):
    parser = argparse.ArgumentParser(
        description="Jurbas-Code: A self-modifying terminal agent."
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear the session history and exit."
    )
    parsed_args = parser.parse_args(args)

    if parsed_args.clear_history:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            print("History cleared.")
        else:
            print("No history file found.")
        return

    load_dotenv()
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()
    
    if provider == "deepseek":
        api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not api_key:
            print("Error: DEEPSEEK_API_KEY environment variable is not set or is empty.")
            sys.exit(1)

    try:
        client = get_client(provider)
    except (ValueError, RuntimeError) as e:
        sys.exit(str(e))

    messages = load_history()
    session_tokens = {"prompt": 0, "completion": 0, "total": 0}

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        save_history(messages)

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
                save_history(messages)

                if not tool_calls:
                    break

            elif provider == "claude":
                anthropic_messages = convert_messages_to_anthropic(messages)
                system_prompt = next((m["content"] for m in messages if m["role"] == "system"), SYSTEM_PROMPT)
                
                try:
                    response = client.messages.create(
                        model="claude-sonnet-4-6",
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
                save_history(messages)
                
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
                save_history(messages)
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
