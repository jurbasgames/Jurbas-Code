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
        self._input_history = []
        self._input_history_index = 0
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
            if not self._input_history or self._input_history[-1] != text:
                self._input_history.append(text)
            self._input_history_index = len(self._input_history)
            self.post_message(self.Submitted(text))
            self.text = ""

    def _history_up(self) -> None:
        if self._input_history and self._input_history_index > 0:
            self._input_history_index -= 1
            self.text = self._input_history[self._input_history_index]
            self.move_cursor((self.document.line_count - 1, len(self.document.get_line(self.document.line_count - 1))))

    def _history_down(self) -> None:
        if self._input_history and self._input_history_index < len(self._input_history) - 1:
            self._input_history_index += 1
            self.text = self._input_history[self._input_history_index]
            self.move_cursor((self.document.line_count - 1, len(self.document.get_line(self.document.line_count - 1))))
        elif self._input_history_index == len(self._input_history) - 1:
            self._input_history_index += 1
            self.text = ""
