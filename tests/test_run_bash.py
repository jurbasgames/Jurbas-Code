import unittest
from unittest.mock import patch, MagicMock
from main import _is_dangerous, _is_readonly_bash, _requires_confirmation, confirm_action, run_bash, web_search


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

        # Test subcommands
        self.assertTrue(_is_readonly_bash("git status"))
        self.assertTrue(_is_readonly_bash("git log"))
        self.assertFalse(_is_readonly_bash("git commit"))
        self.assertFalse(_is_readonly_bash("git push"))
        self.assertFalse(_is_readonly_bash("git branch"))
        self.assertFalse(_is_readonly_bash("git tag"))
        self.assertFalse(_is_readonly_bash("git config user.name X"))
        self.assertFalse(_is_readonly_bash("git branch -d foo"))

        self.assertTrue(_is_readonly_bash("gh pr list"))
        self.assertTrue(_is_readonly_bash("gh pr view 90"))
        self.assertFalse(_is_readonly_bash("gh pr create"))
        self.assertFalse(_is_readonly_bash("gh api repos/foo/bar -X DELETE"))

        self.assertTrue(_is_readonly_bash("pip list"))
        self.assertFalse(_is_readonly_bash("pip install pytest"))

        self.assertTrue(_is_readonly_bash("uv pip list"))
        self.assertFalse(_is_readonly_bash("uv run python main.py"))

        self.assertTrue(_is_readonly_bash("npm list"))
        self.assertFalse(_is_readonly_bash("npm install lodash"))

        self.assertTrue(_is_readonly_bash("cargo tree"))
        self.assertFalse(_is_readonly_bash("cargo build"))

        self.assertTrue(_is_readonly_bash("winget list"))
        self.assertFalse(_is_readonly_bash("winget install curl"))

        # Interpreters alone should be gated/not marked as readonly since they are general-purpose
        self.assertFalse(_is_readonly_bash("python"))
        self.assertFalse(_is_readonly_bash("node"))
        self.assertFalse(_is_readonly_bash("deno"))
        self.assertFalse(_is_readonly_bash("bun"))

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
