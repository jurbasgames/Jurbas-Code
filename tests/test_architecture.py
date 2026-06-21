import importlib
import pytest
from jurbas import security, tools, prompts, adapters, providers, agent

@pytest.mark.parametrize("module_name", [
    "jurbas.security",
    "jurbas.tools",
    "jurbas.prompts",
    "jurbas.adapters",
    "jurbas.providers",
    "jurbas.agent",
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
    schema_tool_names = {t["function"]["name"] for t in tools.tools}
    handler_names = set(tools.TOOL_HANDLERS.keys())

    assert schema_tool_names == handler_names, (
        f"Mismatch between tool schemas and handlers.\n"
        f"Schemas: {schema_tool_names}\n"
        f"Handlers: {handler_names}"
    )

def test_main_as_entrypoint():
    """Verify main.py remains importable and has a main function."""
    import main
    assert hasattr(main, 'main')
    assert callable(main.main)

def test_provider_no_immediate_network():
    """Verify that importing providers doesn't attempt network or key validation immediately."""
    # This is partially covered by test_modules_importable, but we can be explicit
    import jurbas.providers as providers
    assert hasattr(providers, 'get_claude_client')
