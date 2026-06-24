from jurbas_code.prompts import SYSTEM_PROMPT
from jurbas_code.tool_schemas import tools

def test_exported_symbols():
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 0

    assert isinstance(tools, list)
    assert len(tools) == 5

    expected_tool_names = {"read_file", "list_directory", "write_file", "run_bash", "web_search"}
    actual_tool_names = {t["function"]["name"] for t in tools}

    assert actual_tool_names == expected_tool_names

def test_system_prompt_mentions_extracted_package_files():
    assert "main.py" in SYSTEM_PROMPT
    assert "jurbas_code/prompts.py" in SYSTEM_PROMPT
    assert "jurbas_code/tool_schemas.py" in SYSTEM_PROMPT

def test_system_prompt_contains_reasoning_loop():
    prompt_lower = SYSTEM_PROMPT.lower()
    assert "understand" in prompt_lower
    assert "plan" in prompt_lower
    assert "verify" in prompt_lower
    assert "uncertain" in prompt_lower
