from textual.widgets import TextArea
from textual.message import Message
from textual import events

class InputBar(TextArea):
    """Multi-line input area for user commands."""

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = []
        self.history_index = -1
        self.show_line_numbers = False

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            if self.cursor_location[0] == 0:
                self._history_up()
                event.prevent_default()
        elif event.key == "down":
            if self.cursor_location[0] == self.document.line_count - 1:
                self._history_down()
                event.prevent_default()
        elif event.key == "enter":
            self._submit()
            event.prevent_default()
        elif event.key == "shift+enter" or event.key == "ctrl+j":
            self.insert("\n")
            event.prevent_default()

    def _submit(self) -> None:
        text = self.text.strip()
        if text:
            if not self.history or self.history[-1] != text:
                self.history.append(text)
            self.history_index = len(self.history)
            self.post_message(self.Submitted(text))
            self.text = ""

    def _history_up(self) -> None:
        if self.history and self.history_index > 0:
            self.history_index -= 1
            self.text = self.history[self.history_index]
            self.move_cursor((self.document.line_count - 1, len(self.document.get_line(self.document.line_count - 1))))

    def _history_down(self) -> None:
        if self.history and self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.text = self.history[self.history_index]
            self.move_cursor((self.document.line_count - 1, len(self.document.get_line(self.document.line_count - 1))))
        elif self.history_index == len(self.history) - 1:
            self.history_index += 1
            self.text = ""
