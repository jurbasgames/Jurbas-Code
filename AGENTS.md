# Agent Instructions

These instructions apply to the entire repository. They are written for autonomous coding agents and review bots working on Jurbas-Code.

## Operating Rules

1. Work from the current `main` unless the maintainer explicitly asks for a stacked PR or a specific base branch.
2. Keep changes small and directly tied to the requested issue. Do not bundle architecture refactors, dependency updates, formatting churn, generated files, or speculative cleanup with feature/bugfix work.
3. Treat green tests as necessary, not sufficient. Inspect the diff for unrelated behavior changes before opening or updating a PR.
4. Preserve existing behavior, tests, provider paths, docs, and security guardrails unless the task explicitly asks to change them.
5. Do not remove tests to make a PR pass. If a test is wrong, explain why and replace it with a better regression test in the same PR.
6. Do not add new runtime side effects on import or normal startup. In particular, do not run repository analysis, object extraction, network probes, benchmarks, migrations, or file writes during import/startup unless the user explicitly requested that behavior.
7. Do not add loose analysis scripts, generated reports, or scratch artifacts to the runtime package. Files such as `_git_objects.txt`, `_git_analysis.txt`, or ad hoc git-object extraction scripts are out of scope unless requested.
8. Do not expose private shorthand or internal codenames in PRs, issues, commits, or docs. Write explicit technical criteria instead.

## Architecture Guardrails

- `main.py` is the CLI/compatibility entrypoint. Keep it thin.
- Core behavior belongs in packages, not in one-off startup code.
- When touching duplicated paths under `jurbas/` and `jurbas_code/`, inspect both. Do not fix one copy while leaving the other broken.
- Provider-specific request/response conversion belongs in adapter/provider code, not scattered through the CLI.
- File and shell tools must preserve sandbox and confirmation behavior.
- Provider auth must not silently switch billing modes. The Claude provider is intended to use Claude Code OAuth/subscription auth, not Anthropic API-key billing.
- Do not hardcode short-lived provider model IDs without an override path and regression tests.

## Required Validation Before PR

Run the smallest relevant targeted checks plus the full project checks when possible:

```bash
git diff --check
uv run --extra dev python -m py_compile main.py jurbas/*.py jurbas_code/*.py tests/*.py
uv run --extra dev pytest -q
```

For CLI startup changes, also run a no-op startup smoke test and confirm there is no unexpected output or generated file:

```bash
printf 'exit\n' | LLM_PROVIDER=deepseek DEEPSEEK_API_KEY=dummy uv run python main.py
```

Expected behavior for that smoke test: it should print only the prompt and exit. It must not run analysis, create reports, or call a provider API.

## PR Expectations

Every PR should include:

- Problem being fixed.
- Minimal solution summary.
- Files changed and why.
- Exact commands run and their real output summary.
- Known limitations or follow-up work, if any.

Avoid vague claims like “tests pass” without naming the command. Avoid broad rewrites unless the maintainer explicitly requested a rewrite PR.
