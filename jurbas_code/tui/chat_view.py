from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Markdown, Static
from textual.reactive import reactive

class MessageWidget(Static):
    """A widget to display a single chat message."""

    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content

        # Apply base styles for alignment and appearance based on role
        if self.role == "user":
            self.classes = "message user-message"
        elif self.role == "tool":
            self.classes = "message tool-message"
        else:
            self.classes = "message assistant-message"

    def compose(self) -> ComposeResult:
        if self.role == "tool":
            yield Static(f"🔧 Tool Result:\n{self.content}")
        else:
            yield Markdown(self.content)

class ChatView(ScrollableContainer):
    """A scrollable container holding the chat messages."""

    def on_mount(self) -> None:
        pass

    def add_message(self, role: str, content: str) -> MessageWidget:
        msg = MessageWidget(role, content)
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def update_last_message(self, new_content: str) -> None:
        if self.children:
            last_msg = self.children[-1]
            if isinstance(last_msg, MessageWidget):
                last_msg.content = new_content
                # Update the Markdown child
                for child in last_msg.children:
                    if isinstance(child, Markdown):
                        child.update(new_content)
                self.scroll_end(animate=False)
