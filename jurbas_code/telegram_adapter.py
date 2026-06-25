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

    def send_message(self, chat_id: int, text: str) -> None:
        """Sends a message to Telegram, safely chunking if too long (Telegram limit is 4096 chars)."""
        limit = 4000
        parts = [text[i:i+limit] for i in range(0, len(text), limit)]
        for part in parts:
            self._api_call("sendMessage", {"chat_id": chat_id, "text": part})

    def handle_update(self, update: dict) -> None:
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
            # Under Telegram context, we default to block mutating actions to ensure sandbox security,
            # unless we add interactive Telegram markup buttons in the future.
            # Returning False rejects mutating actions gracefully.
            return False

        try:
            agent.chat(
                user_text,
                on_ai_reply=on_ai_reply,
                confirm_handler=confirm_handler
            )
        except Exception as e:
            self.send_message(chat_id, f"Error processing chat: {e}")
            return

        final_reply = "\n\n".join(reply_parts).strip()
        if not final_reply:
            final_reply = "(No response or action completed without output)"

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
