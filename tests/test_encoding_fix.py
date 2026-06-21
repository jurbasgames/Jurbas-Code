import unittest
from unittest.mock import patch, MagicMock
from main import run_bash
import subprocess

class TestRunBashEncoding(unittest.TestCase):
    @patch('subprocess.run')
    def test_run_bash_handles_decoding_error(self, mock_run):
        # Simulate a situation where subprocess.run would raise UnicodeDecodeError
        # if errors='replace' wasn't used.
        # Since we ARE using errors='replace', subprocess.run itself should handle it
        # and return a result with replacement characters.

        # We want to verify that run_bash correctly passes errors='replace' to subprocess.run.
        mock_run.return_value = MagicMock(
            stdout="output with replacement ",
            stderr="",
            returncode=0
        )

        result = run_bash("some command")

        # Check that subprocess.run was called with errors="replace"
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs.get('errors'), 'replace')
        self.assertEqual(result, "output with replacement ")

    def test_real_decoding_replacement(self):
        # On this system (likely Linux/UTF-8), we can try to produce invalid UTF-8
        # and see if subprocess.run with errors='replace' handles it.
        # Note: 'printf "\xff"' produces a single byte 0xFF which is invalid UTF-8.
        # We use a subshell to ensure printf is available and can produce raw bytes.
        result = run_bash('printf "\\xff"')
        # If the system encoding is UTF-8, 0xFF is invalid and will be replaced by \ufffd.
        # If the system encoding is CP1252 or similar, 0xFF might be valid.
        # In our environment, it's UTF-8, so it should be replaced.
        # Let's check for either the replacement char or the original ÿ (if it's cp1252)
        # but the point is it shouldn't CRASH.
        self.assertTrue(len(result) > 0)
        # On most linux it will be \ufffd
        self.assertIn('\ufffd', result)

if __name__ == '__main__':
    unittest.main()
