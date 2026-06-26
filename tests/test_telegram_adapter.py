import pytest
from unittest.mock import MagicMock, patch
import json
import urllib.error

from jurbas_code.telegram_adapter import TelegramAdapter

class MockResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status = status_code

    def read(self):
        return json.dumps(self.data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_telegram_adapter_api_call_success():
    adapter = TelegramAdapter("dummy_token", MagicMock())

    mock_data = {"ok": True, "result": {"message_id": 1}}

    with patch("urllib.request.urlopen", return_value=MockResponse(mock_data)) as mock_urlopen:
        res = adapter._api_call("sendMessage", {"chat_id": 123, "text": "hello"})

        assert res == mock_data
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://api.telegram.org/botdummy_token/sendMessage"
        assert req.get_header("Content-type") == "application/json"


def test_telegram_adapter_api_call_http_error():
    adapter = TelegramAdapter("dummy_token", MagicMock())

    # Create an HTTPError mock that raises when _api_call is executed
    err_response = MagicMock()
    err_response.read.return_value = b'{"description": "Unauthorized"}'

    http_error = urllib.error.HTTPError(
        url="https://api.telegram.org",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=err_response
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        with pytest.raises(RuntimeError) as exc_info:
            adapter._api_call("getUpdates", {})
        assert "Telegram API Error (401): Unauthorized" in str(exc_info.value)


def test_telegram_adapter_handle_update_text_msg():
    mock_agent = MagicMock()
    # Mocking agent chat loop. When chat is called, it triggers on_ai_reply.
    def mock_chat(user_input, on_ai_reply, confirm_handler):
        on_ai_reply("Hello back!")

    mock_agent.chat.side_effect = mock_chat
    agent_factory = lambda: mock_agent

    adapter = TelegramAdapter("dummy_token", agent_factory)

    # We patch _api_call to track output instead of hitting the real endpoint
    with patch.object(adapter, "_api_call") as mock_api_call:
        update = {
            "update_id": 100,
            "message": {
                "chat": {"id": 999},
                "text": "hi"
            }
        }

        adapter.handle_update(update)

        # Verify agent was called
        mock_agent.chat.assert_called_once()

        # Verify sendMessage was called with expected response
        mock_api_call.assert_called_once_with("sendMessage", {
            "chat_id": 999,
            "text": "Hello back!"
        })


def test_telegram_adapter_handle_update_mutating_actions_trigger_markup():
    mock_agent = MagicMock()
    mock_agent.messages = []

    def mock_chat_with_confirm(user_input, on_ai_reply, confirm_handler):
        # Trigger confirm handler to test if it raises interrupt
        confirm_handler("write_file", {"file_path": "a.txt"})
        on_ai_reply("This should not be reached.")

    mock_agent.chat.side_effect = mock_chat_with_confirm
    agent_factory = lambda: mock_agent

    adapter = TelegramAdapter("dummy_token", agent_factory)

    with patch.object(adapter, "_api_call") as mock_api_call:
        update = {
            "message": {
                "chat": {"id": 888},
                "text": "write something"
            }
        }

        adapter.handle_update(update)

        # Verify inline keyboard confirmation was sent
        mock_api_call.assert_called_once_with("sendMessage", {
            "chat_id": 888,
            "text": "⚠️ **Action Confirmation Required**:\nTool: `write_file`\nArguments: `{\n  \"file_path\": \"a.txt\"\n}`",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "✅ Approve", "callback_data": "approve"},
                    {"text": "❌ Decline", "callback_data": "decline"}
                ]]
            }
        })
        # Verify approval is now pending
        assert 888 in adapter.pending_approvals
        assert adapter.pending_approvals[888]["name"] == "write_file"


def test_telegram_adapter_handle_callback_query_approve():
    mock_agent = MagicMock()
    # Tool output mock
    mock_agent.messages = [{"role": "assistant", "tool_calls": [{"id": "tc123", "type": "function", "function": {"name": "write_file"}}]}]

    def mock_chat_continuation(user_input, on_ai_reply, confirm_handler):
        assert user_input == ""
        on_ai_reply("Write completed.")

    mock_agent.chat.side_effect = mock_chat_continuation

    adapter = TelegramAdapter("dummy_token", lambda: mock_agent)
    adapter.pending_approvals[777] = {
        "name": "write_file",
        "args": {"file_path": "a.txt", "content": "hello"},
        "agent": mock_agent
    }

    with patch.object(adapter, "_api_call") as mock_api_call, \
         patch("jurbas_code.tools.write_file", return_value="Success") as mock_write_file:

        callback_update = {
            "callback_query": {
                "id": "query456",
                "data": "approve",
                "message": {
                    "chat": {"id": 777},
                    "message_id": 333,
                    "text": "Previous prompt text"
                }
            }
        }

        adapter.handle_update(callback_update)

        # Verify tool was executed
        mock_write_file.assert_called_once_with("a.txt", "hello")

        # Verify editMessageText was called to clear buttons
        mock_api_call.assert_any_call("editMessageText", {
            "chat_id": 777,
            "message_id": 333,
            "text": "Previous prompt text\n\nDecision: **Approved**"
        })
        # Verify final message sent
        mock_api_call.assert_any_call("sendMessage", {
            "chat_id": 777,
            "text": "Write completed."
        })


def test_telegram_adapter_poll_updates():
    adapter = TelegramAdapter("dummy_token", MagicMock())

    mock_updates_response = {
        "ok": True,
        "result": [
            {
                "update_id": 450,
                "message": {
                    "chat": {"id": 111},
                    "text": "hello"
                }
            }
        ]
    }

    with patch.object(adapter, "_api_call", return_value=mock_updates_response) as mock_api_call, \
         patch.object(adapter, "handle_update") as mock_handle_update:

        adapter.poll()

        # Verify offset updated to last update_id + 1
        assert adapter.offset == 451
        mock_handle_update.assert_called_once_with(mock_updates_response["result"][0])
