from jurbas_code.providers import convert_messages_to_anthropic, convert_to_anthropic_tools


def test_adapters_merge_tool_result_into_existing_user_message():
    messages = [
        {"role": "user", "content": "run tool"},
        {"role": "tool", "tool_call_id": "call_1", "content": "tool output"},
    ]

    anthropic_msgs = convert_messages_to_anthropic(messages)

    assert [m["role"] for m in anthropic_msgs] == ["user"]
    assert anthropic_msgs[0]["content"] == [
        {"type": "text", "text": "run tool"},
        {"type": "tool_result", "tool_use_id": "call_1", "content": "tool output"},
    ]


def test_adapters_handle_missing_tool_schema_fields_and_bad_arguments():
    tools = convert_to_anthropic_tools([
        {"type": "function", "function": {"name": "minimal_tool"}}
    ])
    assert tools[0]["description"] == ""
    assert tools[0]["input_schema"] == {"type": "object", "properties": {}}

    messages = [
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "dict_args", "function": {"name": "tool", "arguments": {"a": 1}}},
            {"id": "bad_args", "function": {"name": "tool", "arguments": "{bad json"}},
        ]},
    ]
    anthropic_msgs = convert_messages_to_anthropic(messages)
    assert anthropic_msgs[0]["content"][0]["input"] == {"a": 1}
    assert anthropic_msgs[0]["content"][1]["input"] == {}
