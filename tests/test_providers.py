import json
import os
import re

import pytest

import providers

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads a file.",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    }
]


def test_require_env_gives_clear_error(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY is not configured"):
        providers.require_env("DEEPSEEK_API_KEY")


def test_claude_headers_match_subscription_routing_shape():
    headers = providers.claude_code_headers()

    assert headers["User-Agent"] == providers.CLAUDE_CODE_USER_AGENT
    assert headers["x-app"] == "cli"
    assert headers["anthropic-version"] == providers.ANTHROPIC_VERSION
    assert headers["anthropic-dangerous-direct-browser-access"] == "true"
    assert "oauth-2025-04-20" in headers["anthropic-beta"]
    assert "cache-diagnosis-2026-04-07" in headers["anthropic-beta"]
    assert UUID_RE.match(headers["X-Claude-Code-Session-Id"])
    assert UUID_RE.match(headers["x-client-request-id"])


def test_claude_refuses_api_key_billing_path(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    with pytest.raises(RuntimeError, match="avoid Anthropic API billing"):
        providers.completion_runner(SAMPLE_TOOLS)


def test_load_claude_token_handles_malformed_credentials(monkeypatch, tmp_path):
    creds_dir = tmp_path / "claude"
    creds_dir.mkdir()
    creds = creds_dir / ".credentials.json"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(creds_dir))

    creds.write_text("[]", encoding="utf-8")
    assert providers.load_claude_code_token() is None

    creds.write_text(json.dumps({"claudeAiOauth": []}), encoding="utf-8")
    assert providers.load_claude_code_token() is None

    creds.write_text(json.dumps({"claudeAiOauth": {"accessToken": "tok"}}), encoding="utf-8")
    assert providers.load_claude_code_token() == "tok"


def test_anthropic_message_conversion_preserves_tool_calls():
    system, messages = providers.anthropic_messages([
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "read it"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "toolu_1",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"file_path": "main.py"}'},
            }],
        },
        {"role": "tool", "tool_call_id": "toolu_1", "name": "read_file", "content": "file"},
    ])

    assert system == "system prompt"
    assert messages[1]["content"][0] == {
        "type": "tool_use",
        "id": "toolu_1",
        "name": "read_file",
        "input": {"file_path": "main.py"},
    }
    assert messages[2]["content"][0]["type"] == "tool_result"


def test_claude_runner_uses_valid_thinking_shape_without_output_config(monkeypatch):
    captured = {}

    def fake_post(token, payload):
        captured["token"] = token
        captured.update(payload)
        return {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}

    monkeypatch.setattr(providers, "post_claude_message", fake_post)
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-token")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    complete = providers.completion_runner(SAMPLE_TOOLS)
    assistant, finish = complete([
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ])

    assert assistant == {"role": "assistant", "content": "ok"}
    assert finish == "end_turn"
    assert captured["token"] == "oauth-token"
    assert captured["model"] == providers.CLAUDE_MODEL
    assert captured["thinking"] == {
        "type": "enabled",
        "budget_tokens": providers.CLAUDE_THINKING_BUDGET_TOKENS,
    }
    assert "output_config" not in captured
    assert captured["tools"][0]["input_schema"]["properties"]["file_path"]["type"] == "string"


def test_anthropic_tool_use_response_becomes_openai_style():
    message = {
        "content": [
            {"type": "text", "text": "I'll read it."},
            {"type": "tool_use", "id": "toolu_1", "name": "read_file", "input": {"file_path": "main.py"}},
        ],
        "stop_reason": "tool_use",
    }

    assistant, finish = providers.openai_style_from_anthropic(message)

    assert finish == "tool_calls"
    assert assistant["content"] == "I'll read it."
    assert assistant["tool_calls"][0]["function"]["name"] == "read_file"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"file_path": "main.py"}
