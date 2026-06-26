from textual.widgets import Static
from textual.app import ComposeResult
from textual.reactive import reactive

class StatusBar(Static):
    """A status bar footer displaying model, tokens, and execution state."""

    provider_model = reactive("Loading...")
    tokens = reactive("Tokens: 0p / 0c")
    is_thinking = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static(id="status-left")
        yield Static(id="status-center")
        yield Static(id="status-right")

    def watch_provider_model(self, provider_model: str) -> None:
        self.query_one("#status-left", Static).update(f"🤖 {provider_model}")

    def watch_tokens(self, tokens: str) -> None:
        self.query_one("#status-right", Static).update(tokens)

    def watch_is_thinking(self, is_thinking: bool) -> None:
        spinner = "⏳ Thinking..." if is_thinking else "🟢 Idle"
        self.query_one("#status-center", Static).update(spinner)
