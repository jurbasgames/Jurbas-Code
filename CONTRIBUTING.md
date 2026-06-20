# Contributing to Jurbas-Code

Thanks for your interest in contributing! 🎉

## 🌿 Branches

- **`main`** — stable branch, always ready for production.
- **Feature branches** — name them in `kebab-case` describing the functionality.
  - Examples: `run-bash-tool`, `streaming-support`, `config-file`.
- Open a **Pull Request (PR)** from your branch to `main` when it's ready, following the `PULL_REQUEST_TEMPLATE.md`.

## 💬 Commit messages

We follow the pattern:

```
<type>[optional scope or emoji]: <description>
```

Example:

```
feat: short and descriptive title, description no longer than 256 characters
```

Based on [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#summary).

## 🔄 PR Process

1. Create a branch from `main`.
2. Make your commits following the pattern above.
3. Open a PR with a descriptive title and clear description:
   - **Summary** (what was done)
   - **Changes** (list of main changes)
   - **How to test** (if applicable)
4. Wait for review.
5. If there are suggestions, make the adjustments and request a new review.
6. After approval, merge using **squash**.

## 🧪 Tests

- Tests live in `tests/`.
- To run them:
  ```bash
  uv run pytest
  ```
- Make sure all tests pass before opening a PR.
- New tests are welcome and encouraged!

### 📦 Dependencies

Install all dependencies (including dev/test tools) with:

```bash
uv sync --all-extras
```

---

## 🐍 Code style

- **Ponytail** — https://github.com/DietrichGebert/ponytail
- Python 3.13+
- We use type hints whenever possible.
- Function and variable names in `snake_case`.
- Class names in `PascalCase`.
- Constants in `UPPER_SNAKE_CASE`.
- Keep functions small and focused (single responsibility principle).
- Docstrings on public functions (simple descriptive style, not necessarily Sphinx).

## 🛡️ Security

- Every file operation uses paths validated by `safe_path()`, which resolves symlinks and enforces a boundary check against `ALLOWED_BASE`.
- Existing files are automatically backed up with a `.bak` suffix before being overwritten.
- Always respect the project sandbox (`ALLOWED_BASE`).

> [!NOTE]
> Additional security features (command blacklist, confirmation gate for mutating actions, shell command sandboxing) are planned — see the roadmap and open PRs for progress.

## ❓ Questions?

Open an issue or ask directly in the PR. We're just a conversation away!
