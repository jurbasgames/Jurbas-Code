import json
import os
from openai import OpenAI


def read_file(file_path: str) -> str:
    """Read file content with security checks."""
    allowed_base = os.path.abspath("./")
    full_path = os.path.abspath(file_path)
    if not full_path.startswith(allowed_base):
        return "Error: path not allowed."
    if not os.path.exists(full_path):
        return f"Error: file '{file_path}' not found."
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)

messages = [
    {"role": "system", "content": ""}
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path of the file to be read (e.g., './example.txt')."
                    }
                },
                "required": ["file_path"],
                "additionalProperties": False
            }
        }
    }
]

while True:
    user_input = input("You: ").strip()
    if user_input.lower() in ("exit", "quit"):
        break
    if not user_input:
        continue

    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=messages,
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        tools=tools,
        tool_choice="auto"
    )

    assistant_msg = response.choices[0].message
    messages.append(assistant_msg)

    if response.choices[0].finish_reason == "tool_calls":
        for tool_call in assistant_msg.tool_calls:
            if tool_call.function.name == "read_file":
                params = tool_call.function.arguments
                params = json.loads(params) if isinstance(
                    params, str) else params
                file_content = read_file(params["file_path"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": "read_file",
                    "content": file_content
                })

        final_response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages
        )
        reply = (final_response.choices[0].message.content or "").strip()
        print(f"AI: {reply}\n")
        messages.append(final_response.choices[0].message)
        continue

    reply = (assistant_msg.content or "").strip()
    print(f"AI: {reply}\n")
