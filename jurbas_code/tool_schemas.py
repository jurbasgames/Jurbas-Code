"""Canonical OpenAI-compatible tool schema for the agent (single source of truth)."""

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
                        "description": "File path (e.g.: './main.py').",
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
                        "description": "Directory path (e.g.: './' for project root).",
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
                        "description": "Path of the file to be written (e.g.: './main.py').",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete content to be written to the file.",
                    },
                },
                "required": ["file_path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Executes a shell command in the project root and returns stdout + stderr. Use for git operations, running tests, or any CLI tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute (e.g.: 'git log --oneline -5').",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web using DuckDuckGo (no API key required). "
                "Use this to look up documentation, find code examples, research topics, "
                "or get up-to-date information from the internet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g.: 'Python asyncio tutorial').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (1-20, default: 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]
