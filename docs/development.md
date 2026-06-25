# Development Workflow and Troubleshooting

This document outlines the standard development process, testing procedures, CI pipeline, and contribution conventions for Jurbas-Code.

## Setting Up the Dev Environment

Jurbas-Code uses `uv` for dependency management and requires Python 3.14.

```bash
# Clone the repository
git clone https://github.com/jurbasgames/Jurbas-Code.git
cd Jurbas-Code

# Sync all dependencies including development extras
uv sync --extra dev --locked --python 3.14
```

## Running Tests

All testing is done via `pytest` and basic python compilation checks to ensure syntax validity.

```bash
# Check syntax
uv run --extra dev --locked --python 3.14 python -m py_compile main.py jurbas_code/*.py tests/*.py

# Run the test suite
uv run --extra dev --locked --python 3.14 pytest -q -v
```

Before opening a PR, always run `git diff --check` to catch trailing whitespace or syntax issues.

## CI Pipeline

Jurbas-Code uses GitHub Actions (`.github/workflows/ci.yml`) to automatically validate changes on push and pull requests to `main` and `dev`.

The pipeline executes the following steps on `ubuntu-latest`:
1. Sets up Python 3.14.
2. Installs `uv`.
3. Syncs dependencies.
4. Runs compile-checks across all Python files.
5. Runs the full `pytest` suite.

## PR Conventions and "Ponytail Standard"

Contributions must adhere strictly to the `AGENTS.md` rules, summarizing the **Ponytail standard**:
- **No AI Slop**: Implement the laziest solution that actually works. Prefer the smallest correct diff over speculative architecture or abstractions.
- **Do not modify tests just to pass CI**: If a test is broken, explain why and fix it correctly.
- **No undocumented side-effects**: Do not add runtime analysis, object extractions, or unrequested file creations during normal startup.
- **Work from `main`**: Unless explicitly requested otherwise.
- **Provide verifiable claims**: Avoid stating "tests pass" without providing the exact commands used and a summary of their real output in your PR description.

## Troubleshooting

- **Provider Billing Errors**: If the `claude` provider fails to initialize, ensure `ANTHROPIC_API_KEY` is not exported in your terminal, as it actively guards against API billing.
- **Token Expiration**: If Claude returns authentication errors, your OAuth token in `~/.claude/.credentials.json` may have expired. Re-run `claude` in your terminal to refresh it.
- **Windows Encoding Issues**: Ensure you are using an up-to-date terminal. Jurbas-Code automatically attempts to reconfigure `sys.stdout` for UTF-8 on Windows.
