# Jurbas-Code

[![Contribute](https://img.shields.io/badge/contribute-CONTRIBUTING.md-blue)](CONTRIBUTING.md)
[![Agent Instructions](https://img.shields.io/badge/agents-AGENTS.md-purple)](AGENTS.md)

Jurbas-Code is an autonomous Python CLI coding agent with streaming support, self-modification capabilities, and multiple LLM providers (Claude Code subscription and DeepSeek). It supports file operations, shell execution, and web search to act as a fully autonomous assistant.

---

## 🚀 Getting Started

### Quick Install

```bash
git clone https://github.com/jurbasgames/Jurbas-Code.git
cd Jurbas-Code
uv sync --all-extras
```

### Quick Start

```bash
# Set your API key or configure Claude Code OAuth
export DEEPSEEK_API_KEY="your-key-here"

# Run the interactive REPL
uv run main.py
```

### Basic Usage

At the `You:` prompt, type a request. The agent will stream its responses and autonomously execute tools when needed.

```text
You: Write a simple script to fetch weather data in weather.py
You: Run pytest and fix any failing tests
You: exit
```

Use `exit` or `quit` to leave the REPL.

---

## 📚 Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

- [**CLI Usage & Tools**](docs/cli_usage.md) - Flags, environment variables, tools, and slash commands.
- [**Providers & Models**](docs/providers.md) - DeepSeek and Claude setup, model resolution.
- [**Architecture**](docs/architecture.md) - Module boundaries and guardrails.
- [**Development Workflow**](docs/development.md) - Dev environment, tests, CI, and PR conventions.

---

## 🤝 How to Contribute

Check the full guide in [`CONTRIBUTING.md`](CONTRIBUTING.md).

Autonomous coding agents and review bots must also read [`AGENTS.md`](AGENTS.md) before changing code. The short version: small PRs, current `main`, real validation, no startup side effects, no speculative refactors.
