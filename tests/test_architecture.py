import importlib
import subprocess
import sys
from pathlib import Path

import pytest
from jurbas_code import security, tools, prompts, providers, agent, tool_schemas

@pytest.mark.parametrize("module_name", [
    "jurbas_code.security",
    "jurbas_code.tools",
    "jurbas_code.prompts",
    "jurbas_code.tool_schemas",
    "jurbas_code.providers",
    "jurbas_code.agent",
    "main",
])
def test_modules_importable(module_name):
    """Verify that all core modules can be imported without side effects."""
    try:
        importlib.import_module(module_name)
    except Exception as e:
        pytest.fail(f"Failed to import {module_name}: {e}")

def test_tool_names_match_handlers():
    """Ensure every tool defined in the schema has a corresponding handler."""
    schema_tool_names = {t["function"]["name"] for t in tool_schemas.tools}
    handler_names = set(tools.TOOL_HANDLERS.keys())

    assert schema_tool_names == handler_names, (
        f"Mismatch between tool schemas and handlers.\n"
        f"Schemas: {schema_tool_names}\n"
        f"Handlers: {handler_names}"
    )


def test_agent_uses_canonical_tool_dispatcher():
    """Agent dispatch must use the canonical handler map from jurbas_code.tools."""
    assert agent.TOOL_HANDLERS is tools.TOOL_HANDLERS


def test_main_as_entrypoint():
    """Verify main.py remains importable and has a main function."""
    import main
    assert hasattr(main, 'main')
    assert callable(main.main)

def test_provider_no_immediate_network():
    """Verify that importing providers doesn't attempt network or key validation immediately."""
    # This is partially covered by test_modules_importable, but we can be explicit
    import jurbas_code.providers as providers
    assert hasattr(providers, 'get_claude_client')


def test_provider_import_does_not_import_security_subprocess():
    """Importing provider-only code must not trigger shell/security import side effects."""
    repo_root = Path(__file__).resolve().parents[1]
    code = (
        "import sys; "
        "import jurbas_code.providers; "
        "raise SystemExit(1 if 'jurbas_code.security' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=repo_root)
    assert result.returncode == 0


def test_no_legacy_claude_3_7_model_hardcode():
    """The Claude 3.7 model id is rejected by the current Claude Code API path."""
    repo_root = Path(__file__).resolve().parents[1]
    offenders = []
    legacy_model = "claude-3-7" "-sonnet-20250219"
    for path in repo_root.rglob("*.py"):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        if legacy_model in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(repo_root)))

    assert offenders == []
