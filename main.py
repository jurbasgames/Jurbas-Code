"""Jurbas-Code — terminal agent with SELF-MODIFICATION capability.

Usage:
    python main.py          # Run interactive REPL
    python main.py --serve  # Same (kept for compatibility)
"""

import json
import os
import sys

# Re-export all public symbols so that ``import main`` and
# ``from main import safe_path`` continue to work (backwards compat).
from jurbas import (           # noqa: F401
    ALLOWED_BASE,
    MAX_TOOL_STEPS,
    safe_path,
    is_secret_path,
    load_dotenv,
    SYSTEM_PROMPT,
    tools,
    TOOL_HANDLERS,
    read_file,
    list_directory,
    write_file,
    run_bash,
)
from jurbas.git_utils import extract_git_info, analyze_pr  # noqa: F401
from openai import OpenAI


# ─── Auto-extract on module load ───
_extracted = False
if os.path.exists(os.path.join(ALLOWED_BASE, ".git")):
    try:
        extract_git_info()
        _extracted = True
    except Exception as e:
        print(f"⚠️ Auto-extract error: {e}")


def main():
    # ─── Load .env if it exists ───
    load_dotenv()

    # ─── DeepSeek Client ───
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ─── Main REPL loop ───
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        for _step in range(MAX_TOOL_STEPS):
            try:
                response_stream = client.chat.completions.create(
                    model="deepseek-v4-flash",
                    messages=messages,
                    stream=True,
                    reasoning_effort="high",
                    extra_body={"thinking": {"type": "enabled"}},
                    tools=tools,
                    tool_choice="auto",
                )
            except Exception as e:
                print(f"AI: Error calling API: {e}\n")
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
                            if getattr(tc_chunk, "function", None):
                                if getattr(tc_chunk.function, "name", None):
                                    tool_calls[index]["function"]["name"] += tc_chunk.function.name
                                if getattr(tc_chunk.function, "arguments", None):
                                    tool_calls[index]["function"]["arguments"] += tc_chunk.function.arguments
            except Exception as e:
                print(f"\n[Stream interrupted: {e}]")
                break

            if printed_ai_prefix:
                print()  # newline after visible response text finishes

            if not content_seen and not content and not reasoning_content and not tool_calls:
                print("AI: Error: No response choices returned from the API.\n")
                break

            # ── Build assistant message dict ──
            assistant_msg_dict: dict = {"role": role}
            if content_seen or content or tool_calls:
                assistant_msg_dict["content"] = content
            if reasoning_content:
                assistant_msg_dict["reasoning_content"] = reasoning_content
            if tool_calls:
                assistant_msg_dict["tool_calls"] = tool_calls

            messages.append(assistant_msg_dict)

            if not tool_calls:
                break

            # ── Execute each tool call ──
            for tool_call in tool_calls:
                name = tool_call["function"]["name"]
                raw_args = tool_call["function"]["arguments"]
                tc_id = tool_call["id"]
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError as e:
                    print(f"  🔧 [{name}] (failed to parse args: {raw_args})")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": name,
                        "content": f"Error: invalid JSON arguments: {e}",
                    })
                    continue
                print(f"  🔧 [{name}] {args}")

                handler = TOOL_HANDLERS.get(name)
                if handler is None:
                    result = f"Error: unknown tool '{name}'."
                else:
                    try:
                        result = handler(args)
                    except KeyError as e:
                        result = f"Error: missing required argument {e} for tool '{name}'."
                    except Exception as e:
                        result = f"Error executing '{name}': {e}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": result,
                })
        else:
            # Loop exhausted without a final (non-tool) response.
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
