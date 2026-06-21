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

    # ─── web_search tests ───

    def test_web_search_no_library(self):
        """Should report missing library gracefully when duckduckgo_search is not installed."""
        with patch('main.HAS_WEB_SEARCH', False):
            result = web_search("test query")
            self.assertIn("not installed", result)
            # Should mention how to install
            self.assertIn("duckduckgo-search", result.lower())

    def test_web_search_empty_query(self):
        """Should reject empty or whitespace-only queries."""
        with patch('main.HAS_WEB_SEARCH', True):
            result = web_search("")
            self.assertIn("non-empty string", result)
            result = web_search("   ")
            self.assertIn("non-empty string", result)

    def test_web_search_non_string_query(self):
        """Should reject non-string queries."""
        with patch('main.HAS_WEB_SEARCH', True):
            result = web_search(123)
            self.assertIn("non-empty string", result)
            result = web_search(None)
            self.assertIn("non-empty string", result)

    def test_web_search_invalid_max_results_clamped(self):
        """max_results out of range (1-20) should be clamped to default 5."""
        with patch('main.HAS_WEB_SEARCH', True):
            with patch('main.DDGS') as mock_ddgs_class:
                mock_instance = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_instance
                mock_instance.text.return_value = []

                # max_results=0 is invalid (<1), should be clamped to 5
                result = web_search("python", max_results=0)
                self.assertIn("No results", result)
                # DDGS.text() should have been called with max_results=5
                mock_instance.text.assert_called_with("python", max_results=5)

    def test_web_search_max_results_too_high_clamped(self):
        """max_results > 20 should be clamped to default 5."""
        with patch('main.HAS_WEB_SEARCH', True):
            with patch('main.DDGS') as mock_ddgs_class:
                mock_instance = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_instance
                mock_instance.text.return_value = []

                result = web_search("python", max_results=100)
                self.assertIn("No results", result)
                mock_instance.text.assert_called_with("python", max_results=5)

    def test_web_search_success(self):
        """Should return formatted results for a valid search."""
        with patch('main.HAS_WEB_SEARCH', True):
            with patch('main.DDGS') as mock_ddgs_class:
                mock_instance = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_instance
                mock_instance.text.return_value = [
                    {"title": "Python Docs", "href": "https://docs.python.org", "body": "Official Python documentation and reference."},
                    {"title": "Real Python", "href": "https://realpython.com", "body": "Python tutorials, courses, and exercises."},
                ]

                result = web_search("python", max_results=2)

                # Verify the output format
                self.assertIn("Web search results for 'python'", result)
                self.assertIn("1. Python Docs", result)
                self.assertIn("https://docs.python.org", result)
                self.assertIn("Official Python documentation", result)
                self.assertIn("2. Real Python", result)
                self.assertIn("https://realpython.com", result)
                self.assertIn("Python tutorials", result)

                # Verify DDGS was called with correct args
                mock_instance.text.assert_called_once_with("python", max_results=2)

    def test_web_search_no_results(self):
        """Should handle empty results gracefully."""
        with patch('main.HAS_WEB_SEARCH', True):
            with patch('main.DDGS') as mock_ddgs_class:
                mock_instance = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_instance
                mock_instance.text.return_value = []

                result = web_search("zzzzzzzzzzz_nonexistent_zzzzzzzz", max_results=3)
                self.assertIn("No results found", result)

    def test_web_search_with_link_fallback(self):
        """Should handle results where the URL key is 'link' instead of 'href'."""
        with patch('main.HAS_WEB_SEARCH', True):
            with patch('main.DDGS') as mock_ddgs_class:
                mock_instance = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_instance
                mock_instance.text.return_value = [
                    {"title": "Example", "link": "https://example.com", "body": "An example site."},
                ]

                result = web_search("example", max_results=1)
                self.assertIn("https://example.com", result)

    def test_web_search_snippet_truncation(self):
        """Long snippets should be truncated at 300 chars."""
        with patch('main.HAS_WEB_SEARCH', True):
            with patch('main.DDGS') as mock_ddgs_class:
                mock_instance = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_instance
                long_body = "x" * 500
                mock_instance.text.return_value = [
                    {"title": "Long Page", "href": "https://long.com", "body": long_body},
                ]

                result = web_search("long", max_results=1)
                # Should contain the truncated version (300 chars + "...")
                self.assertIn("..." + '"' if result.endswith('"') else "...", result)
                self.assertLess(len(result), 380)  # Sanity check: not the full 500 chars

    def test_web_search_api_error(self):
        """Should handle DDGS exceptions gracefully."""
        with patch('main.HAS_WEB_SEARCH', True):
            with patch('main.DDGS') as mock_ddgs_class:
                mock_instance = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_instance
                mock_instance.text.side_effect = Exception("Connection timeout")

                result = web_search("python")
                self.assertIn("Error performing web search", result)
                self.assertIn("Connection timeout", result)


if __name__ == '__main__':
    unittest.main()
