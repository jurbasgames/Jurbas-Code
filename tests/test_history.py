import unittest
import os
import json
from unittest.mock import patch
from main import load_history, save_history, HISTORY_FILE, SYSTEM_PROMPT

class TestHistory(unittest.TestCase):
    def setUp(self):
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)

    def tearDown(self):
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)

    def test_load_history_empty(self):
        messages = load_history()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], SYSTEM_PROMPT)

    def test_save_and_load_history(self):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Hello"}
        ]
        save_history(messages)
        loaded = load_history()
        self.assertEqual(loaded, messages)

    def test_load_history_sync_system_prompt(self):
        old_prompt = "Old Prompt"
        messages = [
            {"role": "system", "content": old_prompt},
            {"role": "user", "content": "Hello"}
        ]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f)

        loaded = load_history()
        self.assertEqual(loaded[0]["content"], SYSTEM_PROMPT)
        self.assertEqual(loaded[1]["content"], "Hello")

    def test_load_history_invalid_json(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("invalid json")
        messages = load_history()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "system")

if __name__ == '__main__':
    unittest.main()
