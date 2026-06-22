import json


def convert_to_anthropic_tools(openai_tools):
    anthropic_tools = []
    for t in openai_tools:
        function = t.get("function", {})
        anthropic_tools.append({
            "name": function.get("name"),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
        })
    return anthropic_tools


def _parse_tool_arguments(raw):
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


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
