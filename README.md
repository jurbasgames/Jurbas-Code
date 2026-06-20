# Jurbas-Code

[![Contribute](https://img.shields.io/badge/contribute-CONTRIBUTING.md-blue)](CONTRIBUTING.md)

An AI terminal agent with streaming support and multiple LLM providers. It is designed to evolve toward a self-evolving, self-benchmarking agent with data-driven self-analysis and human feedback — not just perception-based. Inspired by Hermes from Nous Research.

---

## 🚀 Getting Started

```bash
# Clone the repository
git clone https://github.com/jurbasgames/Jurbas-Code.git
cd Jurbas-Code

# Install dependencies
uv sync --all-extras

# Configure DeepSeek if you want the DeepSeek provider
echo "DEEPSEEK_API_KEY=your-key-here" > .env

# Run with the default provider (claude)
uv run main.py "Hello"
```

## Providers

Available providers:

- `claude` (default) — uses your **Claude Code subscription** OAuth token, not Anthropic API-key billing.
- `deepseek` — uses DeepSeek's OpenAI-compatible API.

Select the provider with `LLM_PROVIDER`:

```bash
LLM_PROVIDER=claude   uv run main.py "Your prompt here"
LLM_PROVIDER=deepseek uv run main.py "Your prompt here"
```

If no prompt argument is provided, the default prompt is `Hello`.

## Provider `claude` — Claude Code subscription

This path does **not** use Anthropic API credits. It reads the OAuth token created by the official Claude Code CLI login:

```bash
claude
```

The token is loaded from:

```text
~/.claude/.credentials.json
```

Specifically:

```text
claudeAiOauth.accessToken
```

Optional overrides:

```bash
export CLAUDE_CODE_OAUTH_TOKEN=<token>
export CLAUDE_CONFIG_DIR=<path-to-claude-config-dir>
```

Important billing guardrail:

```bash
unset ANTHROPIC_API_KEY
```

The Claude provider refuses to run if `ANTHROPIC_API_KEY` is set, because this provider is intended to route through Claude Code subscription auth with `x-app: cli`.

## Provider `deepseek`

```bash
export DEEPSEEK_API_KEY=<your-key>
LLM_PROVIDER=deepseek uv run main.py "Hello"
```

## 🧪 Tests

```bash
uv run pytest
```

Useful focused checks:

```bash
uv run python -m py_compile main.py tests/test_claude_code_headers.py
uv run python -m unittest -v tests/test_claude_code_headers.py
uv run --with pytest pytest -q
```

## 🤝 How to Contribute

Check the full guide in [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 📋 Roadmap

### 1. 🔧 Expand the tool set

| Tool | Description |
|---|---|
| `web_search` | Search the internet |

---

### 2. 📜 Streaming support

Streaming is supported by the provider paths so text appears token by token instead of waiting for full response completion.

---

### 3. 🪵 Logging and persistence system

- Replace `print` with logging levels (DEBUG, INFO, ERROR).
- Save conversation history to a file (e.g. `history.json`) to continue between sessions.
- Handle **token limits**: truncate or summarize old messages.

---

### 4. ⚙️ Configuration file

Externalize API key, model, system prompt and parameters to a `.env` + `config.yaml`:

```yaml
model: "deepseek-v4-pro"
reasoning_effort: "high"
tools_enabled: ["read_file", "write_file", "list_directory"]
```

---

### 5. 🛡️ Security and sandboxing

- Sandboxing and YOLO mode
- Explicit billing guardrails for subscription-backed providers

---

### 6. 🧩 Non-interactive mode

Allow receiving a prompt directly from the command line:

```bash
uv run main.py "Explain the file ./src/utils.py"
```

---

### Compression skills

### Auto Benchmarking

### Memory system with Mnemosyne
