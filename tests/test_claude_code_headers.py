from __future__ import annotations

import os
import pathlib
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jurbas_code import agent


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ClaudeCodeHeadersTests(unittest.TestCase):
    def test_headers_match_interactive_claude_capture(self) -> None:
        headers = agent.claude_code_headers()

        self.assertEqual(headers["User-Agent"], "claude-cli/2.1.183 (external, cli)")
        self.assertEqual(headers["x-app"], "cli")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(headers["anthropic-dangerous-direct-browser-access"], "true")
        self.assertEqual(headers["X-Stainless-Runtime"], "node")
        self.assertEqual(headers["X-Stainless-Runtime-Version"], "v24.3.0")
        self.assertIn("oauth-2025-04-20", headers["anthropic-beta"])
        self.assertIn("cache-diagnosis-2026-04-07", headers["anthropic-beta"])
        self.assertRegex(headers["X-Claude-Code-Session-Id"], UUID_RE)
        self.assertRegex(headers["x-client-request-id"], UUID_RE)

    def test_claude_client_refuses_api_key_billing_path(self) -> None:
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with self.assertRaisesRegex(RuntimeError, "API billing"):
                agent.get_claude_client()


if __name__ == "__main__":
    unittest.main()
