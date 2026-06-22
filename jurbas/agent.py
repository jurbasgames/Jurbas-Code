import json
import os
import sys
from .security import MAX_TOOL_STEPS, _requires_confirmation, confirm_action
from .tools import TOOL_HANDLERS, tools
from .prompts import SYSTEM_PROMPT
from .adapters import (
    convert_to_anthropic_tools,
    convert_messages_to_anthropic,
    normalize_tool_call,
)
from .providers import get_claude_client, CLAUDE_CODE_IDENTITY

from jurbas_code.agent import Agent

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"

def run_agent_loop():
    import main
    main.main()

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
        try:
            user_input = input("You: ").strip()
        except EOFError:
            break

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
                    print(f"  [Tokens] Request: {p_tokens}p / {c_tokens}c ({t_tokens} total) | Session: {session_tokens['prompt']}p / {session_tokens['completion']}c ({session_tokens['total']} total)")

                assistant_msg = response.choices[0].message
                messages.append(assistant_msg.model_dump(exclude_none=True))

                finish = response.choices[0].finish_reason
                if finish != "tool_calls":
                    reply = (assistant_msg.content or "").strip()
                    print(f"AI: {reply}\n")
                    break

                tool_calls = [normalize_tool_call(tc) for tc in (assistant_msg.tool_calls or [])]

            elif provider == "claude":
                anthropic_messages = convert_messages_to_anthropic(messages)
                system_prompt = next((m["content"] for m in messages if m["role"] == "system"), SYSTEM_PROMPT)

                response = client.messages.create(
                    model=os.environ.get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL),
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
