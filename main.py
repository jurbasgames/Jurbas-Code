import os
import sys
from dotenv import load_dotenv
from jurbas_code.agent import (
    Agent,
    get_claude_client,
)

load_dotenv()

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

def on_token_update(p_tokens, c_tokens, t_tokens, session_tokens):
    print(f"  [Tokens] Request: {p_tokens}p / {c_tokens}c ({t_tokens} total) | Session: {session_tokens['prompt']}p / {session_tokens['completion']}c ({session_tokens['total']} total)")

def on_tool_call(name, args, error=None):
    if error:
        print(f"  🔧 [{name}] (failed to parse args: {args})")
    else:
        print(f"  🔧 [{name}] {args}")

def on_ai_reply(reply):
    if reply.startswith("stopped after reaching the max"):
        print(f"AI: {reply}\n")
    else:
        print(f"AI: {reply}\n")

def main():
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()
    
    if provider == "deepseek":
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
    elif provider == "claude":
        try:
            client = get_claude_client()
        except RuntimeError as e:
            sys.exit(f"Erro: {e}")
    else:
        sys.exit(f"Provider desconhecido: {provider}. Use 'claude' ou 'deepseek'.")

    agent = Agent(client, provider)

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

if __name__ == '__main__':
    main()
