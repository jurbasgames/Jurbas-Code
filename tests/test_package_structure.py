from jurbas_code.prompts import SYSTEM_PROMPT
from jurbas_code.tool_schemas import tools

def test_exported_symbols():
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 0

    assert isinstance(tools, list)
    assert len(tools) == 4

    expected_tool_names = {"read_file", "list_directory", "write_file", "run_bash"}
    actual_tool_names = {t["function"]["name"] for t in tools}

    assert actual_tool_names == expected_tool_names

def test_system_prompt_mentions_extracted_package_files():
    assert "main.py" in SYSTEM_PROMPT
    assert "jurbas_code/prompts.py" in SYSTEM_PROMPT
    assert "jurbas_code/tool_schemas.py" in SYSTEM_PROMPT
