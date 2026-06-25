# Jurbas-Code Architecture

This document describes the modular architecture of Jurbas-Code.

## Module Boundaries

The project is organized into the single `jurbas_code/` package to ensure a clean separation of concerns.

### `main.py` (CLI Entrypoint)
- Thin wrapper for the application.
- Loads environment variables (`dotenv`).
- Handles top-level exceptions and user interrupts.
- Builds the client and runs the `Agent` from `jurbas_code.agent`.

### `jurbas_code.agent` (Agent Loop)
- Manages the core conversation loop between the user and the LLM.
- Handles provider selection and initialization.
- Manages token accounting and tool execution flow.

### `jurbas_code.providers` (LLM Providers & Adapters)
- Contains logic for authenticating and initializing LLM clients.
- Currently supports `claude` (via Claude Code auth) and `deepseek` via API key.
- Manages Claude Code credentials loading and custom headers.
- Resolves the provider model and translates messages/tool definitions between
  OpenAI/DeepSeek and Anthropic formats (`convert_*`, `normalize_tool_call`).

### `jurbas_code.tools` (Tool Handlers)
- Implements the available tool set (filesystem, bash execution, web search).
- Maps tool names to their implementation handlers in `TOOL_HANDLERS`.

### `jurbas_code.tool_schemas` (Tool Schemas)
- Contains the canonical JSON schema (`tools`) for the tool definitions sent to the model.

### `jurbas_code.security` (Security & Guardrails)
- Implements path validation (`safe_path`) to prevent directory traversal.
- Defines dangerous command patterns and read-only command lists.
- Manages user confirmation prompts for mutating actions.

### `jurbas_code.prompts` (System Prompts)
- Centralizes the `SYSTEM_PROMPT` used to define agent behavior.

## Architecture Guardrails

Future contributions should respect these boundaries:
- **No Direct Imports from `main.py`**: Other modules should not import from the CLI entrypoint.
- **Provider Independence**: Adapters should handle model-specific quirks, keeping the agent loop generic where possible.
- **Security First**: All new tools that touch the filesystem or execute commands MUST use `jurbas_code.security` for validation.
- **Mocking in Tests**: Infrastructure for providers and tools should be easily mockable for unit testing.
