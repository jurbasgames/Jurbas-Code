import json

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
