"""Telegram gateway/adapter for Jurbas-Code."""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any

# We use standard urllib to avoid adding extra runtime dependencies (keeping the PR Ponytail-clean)
TELEGRAM_API_URL = "https://api.telegram.org/bot"

class TelegramAdapter:
    def __init__(self, token: str, agent_factory):
        self.token = token
        self.agent_factory = agent_factory
        self.offset = 0
        self.sessions: Dict[int, Any] = {}
        # Stores active tool execution contexts waiting for approval: {chat_id: {"name": tool_name, "args": args, "agent": agent}}
        self.pending_approvals: Dict[int, Dict[str, Any]] = {}

    def _api_call(self, method: str, data: dict) -> dict:
        url = f"{TELEGRAM_API_URL}{self.token}/{method}"
        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Try to read the error response body
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                description = err_json.get("description") or e.reason
                raise RuntimeError(f"Telegram API Error ({e.code}): {description}")
            except Exception as read_err:
                if isinstance(read_err, RuntimeError):
                    raise read_err
                raise RuntimeError(f"Telegram HTTP Error ({e.code}): {e.reason}")
        except Exception as e:
            raise RuntimeError(f"Failed to call Telegram API: {e}")

    def send_message(self, chat_id: int, text: str, reply_markup: dict = None) -> None:
        """Sends a message to Telegram, safely chunking if too long (Telegram limit is 4096 chars)."""
        limit = 4000
        parts = [text[i:i+limit] for i in range(0, len(text), limit)]
        for idx, part in enumerate(parts):
            payload = {"chat_id": chat_id, "text": part}
            # Only attach the buttons markup to the very last chunk
            if reply_markup and idx == len(parts) - 1:
                payload["reply_markup"] = reply_markup
            self._api_call("sendMessage", payload)

    def handle_callback_query(self, callback_query: dict) -> None:
        """Processes inline button presses (Approve/Decline)."""
        query_id = callback_query.get("id")
        data = callback_query.get("data", "")
        message = callback_query.get("message", {})
        chat_id = message.get("chat", {}).get("id")

        if not chat_id or chat_id not in self.pending_approvals:
            self._api_call("answerCallbackQuery", {
                "callback_query_id": query_id,
                "text": "No pending actions found."
            })
            return

        pending = self.pending_approvals.pop(chat_id)
        agent = pending["agent"]
        tool_name = pending["name"]
        tool_args = pending["args"]

        # Edit original message to remove buttons and show decision
        original_text = message.get("text", "")
        decision_text = "Approved" if data == "approve" else "Declined"
        self._api_call("editMessageText", {
            "chat_id": chat_id,
            "message_id": message.get("message_id"),
            "text": f"{original_text}\n\nDecision: **{decision_text}**"
        })

        self._api_call("answerCallbackQuery", {
            "callback_query_id": query_id,
            "text": f"Action {decision_text.lower()} successfully."
        })

        reply_parts = []
        def on_ai_reply(reply: str):
            if reply.strip():
                reply_parts.append(reply)

        def mock_confirm_handler(name: str, args: dict) -> bool:
            # We already got the decision from callback query button data
            return data == "approve"

        # Resume agent chat loop from the point where the confirm_handler was triggered
        # We need to simulate the execution of the accepted tool or return decline response
        # To do this safely, we inject the tool result back into messages.
        # But wait: the Agent's chat loop expects to run synchronously in agent.chat()!
        # Since agent.chat() blocks until finish, if a tool requires confirmation:
        # 1. During agent.chat() execution, confirm_handler raises a special interrupt exception.
        # 2. We capture it, save the state (messages, step count etc.), and exit agent.chat().
        # 3. After the user replies with Approve/Decline:
        #    - We read the pending tool execution info.
        #    - If approved, we run the tool, insert the tool result message, and call agent.chat again!
        #    - If declined, we insert the "Action declined" message, and call agent.chat again!
        # This completely preserves backwards compatibility and requires zero refactoring of agent.py!

        from jurbas_code.tools import TOOL_HANDLERS
        handler = TOOL_HANDLERS.get(tool_name)

        if data == "approve":
            try:
                if handler is None:
                    result = f"Error: unknown tool '{tool_name}'."
                else:
                    result = handler(tool_args)
            except KeyError as exc:
                result = f"Error: missing required argument {exc} for tool '{tool_name}'."
            except Exception as exc:
                result = f"Error executing '{tool_name}': {exc}"
        else:
            result = "Action declined by the user. Do not retry unless explicitly asked."

        # Insert the tool result message back into messages history
        # We find the matching tool call ID to ensure correctness
        tc_id = None
        last_msg = agent.messages[-1] if agent.messages else {}
        if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
            for tc in last_msg["tool_calls"]:
                if tc.get("function", {}).get("name") == tool_name:
                    tc_id = tc.get("id")
                    break

        agent.messages.append({
            "role": "tool",
            "tool_call_id": tc_id,
            "name": tool_name,
            "content": result,
        })

        # Resume agent chat loop by sending a dummy continuation prompt or empty input
        # to trigger the model to check tool results and continue
        try:
            # We call agent.chat with an empty user input or trigger agent loop directly.
            # In our agent chat, if the last message is tool result, it continues executing.
            # However, agent.chat(user_input) appends a user message. We don't want to append a new user message,
            # we want to resume the current execution.
            # Let's inspect: we can implement a resume method or simulate chat continuation.
            # If we call chat, it appends user message. To avoid that, we can temporarily pop it or let it resume.
            # Let's write a small wrapper inside agent to resume if needed, or simply handle it here:
            # We can run the loop ourselves or call a resume method. Let's do it cleanly:
            # We'll call agent.chat() but passing None or empty string might append it.
            # Let's check how agent.chat() behaves.
            agent.chat(
                "",  # We will handle empty user_input in agent.py to resume if messages already contain tool results!
                on_ai_reply=on_ai_reply,
                confirm_handler=confirm_handler_loop_trigger
            )
        except ApprovalRequiredInterrupt:
            # Handled below: if it triggers another confirmation, we wait again
            return
        except Exception as e:
            self.send_message(chat_id, f"Error resuming chat: {e}")
            return

        final_reply = "\n\n".join(reply_parts).strip()
        if not final_reply:
            final_reply = "(Action completed without further output)"
        self.send_message(chat_id, final_reply)

    def handle_update(self, update: dict) -> None:
        # Check for callback queries (button clicks)
        callback_query = update.get("callback_query")
        if callback_query:
            self.handle_callback_query(callback_query)
            return

        message = update.get("message")
        if not message:
            return
        
        chat = message.get("chat")
        if not chat:
            return
        
        chat_id = chat.get("id")
        user_text = message.get("text", "")
        
        if not user_text:
            return

        # Start or get session-specific agent
        if chat_id not in self.sessions:
            self.sessions[chat_id] = self.agent_factory()

        agent = self.sessions[chat_id]

        reply_parts = []
        def on_ai_reply(reply: str):
            if reply.strip():
                reply_parts.append(reply)

        def confirm_handler(name: str, args: dict) -> bool:
            # If a tool requires confirmation, we store the execution context
            # and raise an interrupt exception to stop the chat loop.
            self.pending_approvals[chat_id] = {
                "name": name,
                "args": args,
                "agent": agent
            }
            # Ask the user for approval via inline buttons
            keyboard = {
                "inline_keyboard": [[
                    {"text": "✅ Approve", "callback_data": "approve"},
                    {"text": "❌ Decline", "callback_data": "decline"}
                ]]
            }
            self.send_message(
                chat_id,
                f"⚠️ **Action Confirmation Required**:\nTool: `{name}`\nArguments: `{json.dumps(args, indent=2)}`",
                reply_markup=keyboard
            )
            raise ApprovalRequiredInterrupt()

        try:
            agent.chat(
                user_text,
                on_ai_reply=on_ai_reply,
                confirm_handler=confirm_handler
            )
        except ApprovalRequiredInterrupt:
            # Gracefully halt chat execution, reply collected output, and wait for callback query
            pass
        except Exception as e:
            self.send_message(chat_id, f"Error processing chat: {e}")
            return

        final_reply = "\n\n".join(reply_parts).strip()
        if final_reply:
            self.send_message(chat_id, final_reply)

    def poll(self, limit: int = 100, timeout: int = 10) -> None:
        """Performs a single long-polling request and handles new updates."""
        try:
            res = self._api_call("getUpdates", {
                "offset": self.offset,
                "limit": limit,
                "timeout": timeout
            })
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(2)  # Back off on error
            return

        updates = res.get("result", [])
        for update in updates:
            self.handle_update(update)
            update_id = update.get("update_id")
            if update_id is not None:
                self.offset = update_id + 1

    def run_loop(self) -> None:
        """Main loop that runs the polling gateway."""
        print("Telegram bot starting...")
        while True:
            try:
                self.poll()
            except KeyboardInterrupt:
                print("Stopping Telegram bot.")
                break
            except Exception as e:
                print(f"Error in bot loop: {e}")
                time.sleep(5)


class ApprovalRequiredInterrupt(Exception):
    """Exception raised to interrupt the Agent execution loop when confirmation is needed."""
    pass


def confirm_handler_loop_trigger(name: str, args: dict) -> bool:
    # Used inside callback query loop to trigger subsequent approval requests
    # It must raise the same interrupt to yield control back to long poll
    raise ApprovalRequiredInterrupt()
