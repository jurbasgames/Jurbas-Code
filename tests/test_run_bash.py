import unittest
from unittest.mock import patch
from jurbas.security import _is_dangerous, _is_readonly_bash, _requires_confirmation, confirm_action
from jurbas.tools import run_bash

class TestMain(unittest.TestCase):
    def test_is_dangerous(self):
        self.assertIsNotNone(_is_dangerous("ls | sudo tee file"))
        self.assertIsNotNone(_is_dangerous("cat file | bash"))
        self.assertIsNotNone(_is_dangerous("cat file |   sudo -i"))
        self.assertIsNone(_is_dangerous("ls | grep something"))

    def test_dangerous_patterns(self):
        self.assertIsNotNone(_is_dangerous("echo ok && rm -rf /"))
        self.assertIsNotNone(_is_dangerous("rm -rf /"))

    def test_is_readonly_bash(self):
        self.assertFalse(_is_readonly_bash(123))
        self.assertFalse(_is_readonly_bash(None))
        self.assertTrue(_is_readonly_bash("ls -la"))
        self.assertFalse(_is_readonly_bash("ls -la && echo ok"))
        self.assertFalse(_is_readonly_bash("rm -rf /"))

    def test_requires_confirmation(self):
        self.assertTrue(_requires_confirmation("write_file", {"file_path": "a.txt", "content": "a"}))
        self.assertTrue(_requires_confirmation("run_bash", {"command": "echo ok && ls"}))
        self.assertFalse(_requires_confirmation("run_bash", {"command": "ls"}))
        # Non-dict args should require confirmation to be safe
        self.assertTrue(_requires_confirmation("run_bash", "echo ok"))
        self.assertTrue(_requires_confirmation("run_bash", 123))
        self.assertTrue(_requires_confirmation("write_file", None))

    def test_run_bash_non_string(self):
        self.assertEqual(run_bash(123), "Error: command must be a string.")
        self.assertEqual(run_bash(None), "Error: command must be a string.")

    @patch('builtins.input', return_value='y')
    def test_confirm_action(self, mock_input):
        self.assertTrue(confirm_action("run_bash", {"command": "ls"}))
        self.assertTrue(confirm_action("run_bash", "ls")) # Non-dict
        self.assertTrue(confirm_action("run_bash", None)) # Non-dict

if __name__ == '__main__':
    unittest.main()
