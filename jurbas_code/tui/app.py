import os
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual import work

from jurbas_code.agent import Agent
from jurbas_code.providers import get_client, resolve_provider_model
from jurbas_code.tui.chat_view import ChatView, MessageWidget
from jurbas_code.tui.input_bar import InputBar
from jurbas_code.tui.status_bar import StatusBar

class JurbasTUI(App):
    """Textual app for Jurbas-Code."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #chat-container {
        height: 1fr;
        border: solid green;
    }

    InputBar {
        height: 10;
        border: solid yellow;
        dock: bottom;
    }

    StatusBar {
        height: 1;
        dock: bottom;
        layout: horizontal;
        background: $boost;
    }

    #status-left {
        width: 1fr;
        content-align: left middle;
    }

    #status-center {
        width: 1fr;
        content-align: center middle;
    }

    #status-right {
        width: 1fr;
        content-align: right middle;
    }

    .message {
        margin: 1 2;
        padding: 1 2;
        border: solid $accent;
    }

    .user-message {
        border-title-color: green;
        border-title-align: right;
    }

    .assistant-message {
        border-title-color: blue;
        border-title-align: left;
    }

    .tool-message {
        border-title-color: yellow;
        border-title-align: left;
    }
    """

    def __init__(self, agent: Agent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-container"):
            yield ChatView(id="chat-view")
        yield InputBar(id="input-bar")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.title = "Jurbas-Code"
        status_bar = self.query_one(StatusBar)
        provider = self.agent.provider
        model = resolve_provider_model(provider, self.agent.client)
        status_bar.provider_model = f"{provider} ({model})"

        chat_view = self.query_one(ChatView)
        for msg in self.agent.messages:
            role = msg.get("role")
            if role == "system":
                continue
            content = msg.get("content", "")
            if role in ("user", "assistant", "tool") and content:
                ui_msg = chat_view.add_message(role, content)
                ui_msg.border_title = role.capitalize()

            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                name = tc.get("function", {}).get("name", "unknown")
                args = tc.get("function", {}).get("arguments", "")
                ui_msg = chat_view.add_message("assistant", f"*(Tool call: `{name}`)*\n```json\n{args}\n```")
                ui_msg.border_title = "Assistant"

        self.query_one(InputBar).focus()

    def on_input_bar_submitted(self, message: InputBar.Submitted) -> None:
        text = message.text.strip()
        if text.lower() in ("/quit", "/exit"):
            self.exit()
            return

        is_slash_command = text.startswith("/")
        if not is_slash_command:
            chat_view = self.query_one(ChatView)
            ui_msg = chat_view.add_message("user", text)
            ui_msg.border_title = "User"

        self.query_one(StatusBar).is_thinking = True
        self.run_agent(text)

    @work(thread=True)
    def run_agent(self, user_input: str) -> None:
        chat_view = self.query_one(ChatView)
        status_bar = self.query_one(StatusBar)

        current_ai_msg = None
        current_ai_text = ""

        def update_ui():
            if current_ai_msg and current_ai_text:
                self.call_from_thread(chat_view.update_last_message, current_ai_text)

        def on_token_update(p_tokens, c_tokens, t_tokens, session_tokens):
            tokens_str = f"Tokens: {session_tokens['prompt']}p / {session_tokens['completion']}c"
            self.call_from_thread(setattr, status_bar, "tokens", tokens_str)

        def on_tool_call(name, args, error=None):
            nonlocal current_ai_msg, current_ai_text
            import sys
            msg_text = f"*(Tool call: `{name}`)*\n```json\n{args}\n```"
            if error:
                msg_text += f"\n*(Error parsing args: {error})*"

            def add_tool_call():
                ui_msg = chat_view.add_message("assistant", msg_text)
                ui_msg.border_title = "Assistant"

            self.call_from_thread(add_tool_call)
            current_ai_msg = None
            current_ai_text = ""
            if hasattr(sys.stdout, "buffer_text"):
                sys.stdout.buffer_text = ""

        def on_tool_result(name, result):
            def add_tool_result():
                ui_msg = chat_view.add_message("tool", result)
                ui_msg.border_title = f"Tool ({name})"
            self.call_from_thread(add_tool_result)

        def on_ai_reply(reply):
            nonlocal current_ai_msg, current_ai_text

            if getattr(self.agent, "session_model", None):
                new_label = f"{self.agent.provider} ({self.agent.session_model})"
                self.call_from_thread(setattr, status_bar, "provider_model", new_label)
            if not current_ai_msg:
                def add_msg():
                    nonlocal current_ai_msg
                    current_ai_msg = chat_view.add_message("assistant", reply)
                    current_ai_msg.border_title = "Assistant"
                self.call_from_thread(add_msg)
            else:
                current_ai_text = reply
                update_ui()

        # Simple monkey patch to capture streaming print statements from agent if needed
        # We'll just rely on the callbacks for now, and patch standard output for streaming
        import sys
        import io

        class StreamCapturer(io.StringIO):
            def __init__(self, callback):
                super().__init__()
                self.callback = callback
                self.buffer_text = ""

            def write(self, s):
                self.buffer_text += s
                self.callback(self.buffer_text)
                return len(s)

            def flush(self):
                pass

        def stream_update(text):
            nonlocal current_ai_msg, current_ai_text
            # Strip "AI: " prefixes that agent might print
            clean_text = text.replace("AI: ", "")
            current_ai_text = clean_text

            if not current_ai_msg and clean_text.strip():
                def add_msg():
                    nonlocal current_ai_msg
                    current_ai_msg = chat_view.add_message("assistant", clean_text)
                    current_ai_msg.border_title = "Assistant"
                self.call_from_thread(add_msg)
            elif current_ai_msg:
                update_ui()

        original_stdout = sys.stdout
        sys.stdout = StreamCapturer(stream_update)

        try:
            self.agent.chat(
                user_input,
                on_token_update=on_token_update,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_ai_reply=on_ai_reply,
            )
        finally:
            sys.stdout = original_stdout
            self.call_from_thread(setattr, status_bar, "is_thinking", False)
