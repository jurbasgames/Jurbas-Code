"""Jurbas-Code — terminal agent with SELF-MODIFICATION capability.

Usage:
    python main.py          # Run interactive REPL
    python main.py --serve  # Same (kept for compatibility)
"""

import argparse
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

try:
    from duckduckgo_search import DDGS
    HAS_WEB_SEARCH = True
except ImportError:
    DDGS = None
    HAS_WEB_SEARCH = False

# Re-export all public symbols so that ``import main`` and
# ``from main import safe_path`` continue to work (backwards compat).
from jurbas_code import (      # noqa: F401
    __version__,
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
    tools_schema as tools,
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

from openai import AuthenticationError, APIError, RateLimitError, APITimeoutError
from jurbas_code.agent import Agent

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

def on_token_update(p_tokens, c_tokens, t_tokens, session_tokens):
    print(f"  [Tokens] Request: {p_tokens}p / {c_tokens}c ({t_tokens} total) | Session: {session_tokens['prompt']}p / {session_tokens['completion']}c ({session_tokens['total']} total)")

def on_tool_call(name, args, error=None):
    if error:
        print(f"  🔧 [{name}] (failed to parse args: {args})")
    else:
        print(f"  🔧 [{name}] {args}")

def on_ai_reply(reply):
    print(f"AI: {reply}\n")

def main(args=None):
    parser = argparse.ArgumentParser(
        description="Jurbas-Code: A self-modifying terminal agent."
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear the session history and exit."
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Jurbas-Code v{__version__}",
        help="Show the program version and exit."
    )
    parsed_args = parser.parse_args([] if args is None else args)

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

    agent = Agent(client, provider)
    agent.messages = load_history()

    print(f"Jurbas-Code v{__version__}")

    while True:
        try:
            user_input = input("You: ").strip()
        except EOFError:
            break

        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        agent.chat(
            user_input,
            on_token_update=on_token_update,
            on_tool_call=on_tool_call,
            on_ai_reply=on_ai_reply,
            confirm_handler=confirm_action
        )
        save_history(agent.messages)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        main(sys.argv[2:])
    else:
        main(sys.argv[1:])
