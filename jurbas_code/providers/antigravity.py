import os
from typing import Any
from openai import OpenAI, AuthenticationError

class AntigravityProvider:
    def __init__(self):
        self.api_key = os.environ.get("ANTIGRAVITY_API_KEY")
        self.base_url = os.environ.get("ANTIGRAVITY_BASE_URL", "https://api.antigravity.ai")

    def get_client(self) -> OpenAI:
        if not self.api_key:
            # We raise a RuntimeError to be consistent with get_claude_client
            # while still providing a clear authentication-related message.
            raise RuntimeError("ANTIGRAVITY_API_KEY environment variable is not set.")

        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
