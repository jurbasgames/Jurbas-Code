# Jurbas-Code

[![Contribute](https://img.shields.io/badge/contribute-CONTRIBUTING.md-blue)](CONTRIBUTING.md)

An AI terminal agent with self-modification capability, API-model based to evolve its own skills. A self-evolving, self-benchmarking AI agent with data-driven self-analysis and human feedback for real evolution — not just perception-based. Inspired by Hermes from Nous Research.

---

## 🚀 Getting Started

```bash
# Clone the repository
git clone https://github.com/jurbasgames/Jurbas-Code.git
cd Jurbas-Code

# Configure your API key
echo "DEEPSEEK_API_KEY=your-key-here" > .env

# Install dependencies
uv sync

# Run
python main.py
```

## 🧪 Tests

```bash
uv run --extra dev pytest
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

### 2. 📜 Streaming support (in progress)

Currently the response appears all at once. With streaming, text appears token by token, improving the experience:

```python
response = client.chat.completions.create(..., stream=True)
for chunk in response:
    ...
```

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

---

### 6. 🧩 Non-interactive mode

Allow receiving a prompt directly from the command line:

```bash
python main.py "Explain the file ./src/utils.py"
```

---

### Compression skills

### Auto Benchmarking

### Memory system with Mnemosyne
