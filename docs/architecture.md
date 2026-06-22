# Jurbas-Code Architecture

This document describes the modular architecture of Jurbas-Code.

## Module Boundaries

The project is organized into the `jurbas/` package to ensure a clean separation of concerns.

### `main.py` (CLI Entrypoint)
- Thin wrapper for the application.
- Loads environment variables (`dotenv`).
- Handles top-level exceptions and user interrupts.
- Invokes the agent loop from `jurbas.agent`.

### `jurbas.agent` (Agent Loop)
- Manages the core conversation loop between the user and the LLM.
- Handles provider selection and initialization.
- Manages token accounting and tool execution flow.
- Extracted from the original monolithic `main.py`.

### `jurbas.providers` (LLM Providers)
- Contains logic for authenticating and initializing LLM clients.
- Currently supports `claude` (via Claude Code auth) and `deepseek`.
- Manages Claude Code credentials loading and custom headers.

### `jurbas.adapters` (Model Adapters)
- Provides translation layers between different LLM API formats.
- Converts messages and tool definitions between OpenAI/DeepSeek and Anthropic formats.
- Normalizes tool call objects for consistent handling.

### `jurbas.tools` (Tool Handlers & Schemas)
- Defines the available tool set (filesystem, bash execution).
- Contains the JSON schemas for tool definitions.
- Maps tool names to their implementation handlers in `TOOL_HANDLERS`.

### `jurbas.security` (Security & Guardrails)
- Implements path validation (`safe_path`) to prevent directory traversal.
- Defines dangerous command patterns and read-only command lists.
- Manages user confirmation prompts for mutating actions.

### `jurbas.prompts` (System Prompts)
- Centralizes the `SYSTEM_PROMPT` used to define agent behavior.

## Architecture Guardrails

Future contributions should respect these boundaries:
- **No Direct Imports from `main.py`**: Other modules should not import from the CLI entrypoint.
- **Provider Independence**: Adapters should handle model-specific quirks, keeping the agent loop generic where possible.
- **Security First**: All new tools that touch the filesystem or execute commands MUST use `jurbas.security` for validation.
- **Mocking in Tests**: Infrastructure for providers and tools should be easily mockable for unit testing.
