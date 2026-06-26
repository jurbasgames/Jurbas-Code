# CLI Usage & Tools

Jurbas-Code provides a command-line interface to interact with the autonomous coding agent. This guide covers CLI flags, environment variables, available tools, and slash commands.

## CLI Flags

You can run Jurbas-Code interactively by invoking `main.py`.

```bash
uv run main.py [FLAGS]
```

### Available Flags:

- `--clear-history`: Clears the existing conversation history (`history.json`) and exits. Useful for starting a fresh session.
- `--version`, `-v`: Shows the program version and exits.
- `--telegram`: Runs Jurbas-Code as a Telegram Bot gateway (requires `TELEGRAM_BOT_TOKEN`).
- `--serve`: Runs the interactive REPL (kept for backwards compatibility).

## Environment Variables

Jurbas-Code's behavior can be customized using environment variables. You can set them inline, export them, or define them in a `.env` file.

### General Configuration

- `LLM_PROVIDER`: Selects the LLM provider to use. Valid options are `claude` (default) or `deepseek`.

### Claude Provider (`LLM_PROVIDER=claude`)

- `CLAUDE_CODE_OAUTH_TOKEN`: Optional override for the Claude Code OAuth token.
- `CLAUDE_CONFIG_DIR`: Path to the Claude config directory (defaults to `~/.claude`).
- `ANTHROPIC_API_KEY`: **Must be unset**. The Claude provider routes through Claude Code subscription authentication (`x-app: cli`) and actively refuses to run if this key is set to prevent API billing.

### DeepSeek Provider (`LLM_PROVIDER=deepseek`)

- `DEEPSEEK_API_KEY`: Your DeepSeek API key. Required when using the DeepSeek provider.

### Telegram Gateway (`--telegram`)

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token.
- `JURBAS_TELEGRAM_ALLOWED_USERS`: A JSON-formatted list of allowed Telegram user or chat IDs (e.g., `[123456, 789012]`). If set, only these IDs will have access to the bot.

## Available Tools

The agent has access to a set of internal tools it can invoke autonomously to explore the codebase, write code, and search the web.

- `read_file`: Reads the contents of a file (handles large file truncation to avoid token limits).
- `write_file`: Creates or overwrites a file with specific content.
- `list_directory`: Lists the contents of a directory.
- `run_bash`: Executes a shell command in the local environment. By design, mutative commands require user confirmation.
- `web_search`: Searches the internet for information (useful for fetching up-to-date documentation or solving errors).

## Examples

**1. Starting a standard session (Claude provider):**
```bash
uv run main.py
```

**2. Starting with DeepSeek and clearing previous history:**
```bash
export DEEPSEEK_API_KEY="sk-..."
LLM_PROVIDER=deepseek uv run main.py --clear-history
```

**3. Requesting a specific task directly via the REPL:**
```text
You: Find the model resolution logic in providers.py and explain it.
```

**4. Running as a Telegram Bot:**
```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
uv run main.py --telegram
```
