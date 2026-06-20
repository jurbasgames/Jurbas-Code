import json
import os
import shutil
from openai import OpenAI

# ─── Security configuration ───
ALLOWED_BASE = os.path.realpath("./")
MAX_TOOL_STEPS = 25  # safety cap on consecutive tool-call iterations


def safe_path(file_path: str) -> str:
    """Resolves and validates a path within the allowed directory.

    Uses realpath so that symlinks are resolved before the boundary check,
    preventing a symlink inside the project from pointing outside it.
    """
    full = os.path.realpath(file_path)
    if os.path.commonpath([ALLOWED_BASE, full]) != ALLOWED_BASE:
        raise PermissionError(f"Path not allowed: {file_path}")
    return full


# ─── Tools ───

def read_file(file_path: str) -> str:
    """Read file content with security checks."""
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(full):
        return f"Error: file '{file_path}' not found."
    try:
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(dir_path: str) -> str:
    """Lists files and folders in the specified directory."""
    try:
        full = safe_path(dir_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(full):
        return f"Error: directory '{dir_path}' not found."
    if not os.path.isdir(full):
        return f"Error: '{dir_path}' is not a directory."
    try:
        items = []
        for name in sorted(os.listdir(full)):
            item_path = os.path.join(full, name)
            kind = "DIR" if os.path.isdir(item_path) else "FILE"
            size = ""
            if kind == "FILE":
                try:
                    size_bytes = os.path.getsize(item_path)
                    if size_bytes < 1024:
                        size = f" ({size_bytes} B)"
                    elif size_bytes < 1024 * 1024:
                        size = f" ({size_bytes / 1024:.1f} KB)"
                    else:
                        size = f" ({size_bytes / 1024 / 1024:.1f} MB)"
                except OSError:
                    size = " (unknown size)"

            items.append(f"  [{kind}] {name}{size}")
        return f"Contents of '{dir_path}' ({len(items)} items):\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {e}"


def write_file(file_path: str, content: str) -> str:
    """Writes content to a file (creates parent directories if needed)."""
    try:
        full = safe_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        # Back up an existing file before overwriting so a bad generation
        # (e.g. self-modifying main.py) can be recovered.
        backup_note = ""
        if os.path.exists(full):
            backup = full + ".bak"
            shutil.copy2(full, backup)
            backup_note = f" (previous version backed up to '{os.path.basename(backup)}')"
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(full)
        return f"File '{file_path}' written successfully ({size} bytes).{backup_note}"
    except Exception as e:
        return f"Error writing file: {e}"


# ─── Tool mapping ───
TOOL_HANDLERS = {
    "read_file": lambda args: read_file(args["file_path"]),
    "list_directory": lambda args: list_directory(args["dir_path"]),
    "write_file": lambda args: write_file(args["file_path"], args["content"]),
}

# ─── System Prompt ───
SYSTEM_PROMPT = (
    "You are a terminal agent with SELF-MODIFICATION capability. "
    "You can read, list, and WRITE files — including your own source code (main.py). "
    "Your purpose is to evolve your own capabilities: when the user asks for a new feature, "
    "read your current code, generate a modified version, and overwrite the corresponding file.\n\n"
    "Rules:\n"
    "- Always read main.py before modifying it to understand the current state.\n"
    "- Think carefully before writing: the code must compile and run.\n"
    "- Maintain the existing style and structure when adding tools.\n"
    "- When finished with a modification, explain what was changed.\n"
    "- Always respond in English.\n"
    "- Use list_directory to explore the project structure."
)

# ─── Tool definitions (OpenAI schema) ───
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path (e.g.: './main.py')."
                    }
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Directory path (e.g.: './' for project root)."
                    }
                },
                "required": ["dir_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a file. Creates parent directories if needed. Use to modify your own code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path of the file to be written (e.g.: './main.py')."
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete content to be written to the file."
                    },
                },
                "required": ["file_path", "content"],
                "additionalProperties": False,
            },
        },
    },
]


def main():
    # ─── DeepSeek Client ───
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    # ─── Initial history ───
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # ─── Main loop ───
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # ── Tool call loop (allows multiple steps, bounded for safety) ──
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
            reasoning_content = ""
            tool_calls = []
            finish_reason = None

            print("AI: ", end="", flush=True)
            try:
                for chunk in response_stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if getattr(delta, "role", None):
                        role = delta.role
                    if getattr(chunk.choices[0], "finish_reason", None) is not None:
                        finish_reason = chunk.choices[0].finish_reason

                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        reasoning_content += reasoning
                        print(reasoning, end="", flush=True)

                    if getattr(delta, "content", None) is not None:
                        content += delta.content
                        print(delta.content, end="", flush=True)

                    tool_calls_chunk = getattr(delta, "tool_calls", None)
                    if tool_calls_chunk:
                        for tc_chunk in tool_calls_chunk:
                            index = tc_chunk.index
                            while len(tool_calls) <= index:
                                tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
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

            print()  # newline after response finishes

            if not content and not reasoning_content and not tool_calls:
                print("AI: Error: No response choices returned from the API.\n")
                break

            assistant_msg_dict = {"role": role}
            if content:
                assistant_msg_dict["content"] = content
            if reasoning_content:
                assistant_msg_dict["reasoning_content"] = reasoning_content
            if tool_calls:
                assistant_msg_dict["tool_calls"] = tool_calls

            messages.append(assistant_msg_dict)

            if finish_reason != "tool_calls" and not tool_calls:
                break

            for tool_call in tool_calls:
                name = tool_call["function"]["name"]
                raw_args = tool_call["function"]["arguments"]
                tc_id = tool_call["id"]
                try:
                    args = json.loads(raw_args) if isinstance(
                        raw_args, str) else raw_args
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
            print(
                f"AI: stopped after reaching the max of {MAX_TOOL_STEPS} tool steps.\n")


if __name__ == '__main__':
    main()
