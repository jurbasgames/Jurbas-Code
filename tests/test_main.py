import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import os

class TestMain(unittest.TestCase):
    def setUp(self):
        # Force re-import of main for every test case so top-level code runs
        if 'main' in sys.modules:
            del sys.modules['main']

    @patch('os.environ.get')
    @patch('openai.OpenAI')
    @patch('builtins.print')
    def test_main_success(self, mock_print, mock_openai, mock_env_get):
        # Setup mocks for a successful run
        mock_env_get.return_value = 'test_api_key'

        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Mocked response"
        mock_client_instance.chat.completions.create.return_value = mock_response

        # Act
        import main

        # Verify
        mock_env_get.assert_called_with('DEEPSEEK_API_KEY')
        mock_openai.assert_called_once_with(
            api_key='test_api_key',
            base_url="https://api.deepseek.com"
        )

        mock_client_instance.chat.completions.create.assert_called_once_with(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )

        mock_print.assert_called_once_with("Mocked response")

    @patch('os.environ.get')
    @patch('openai.OpenAI')
    @patch('builtins.print')
    def test_main_missing_api_key(self, mock_print, mock_openai, mock_env_get):
        # Setup mocks for missing API key
        mock_env_get.return_value = None

        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance

        # Act
        import main

        # Verify
        mock_env_get.assert_called_with('DEEPSEEK_API_KEY')
        mock_openai.assert_called_once_with(
            api_key=None,
            base_url="https://api.deepseek.com"
        )

    @patch('os.environ.get')
    @patch('openai.OpenAI')
    @patch('builtins.print')
    def test_main_api_exception(self, mock_print, mock_openai, mock_env_get):
        # Setup mocks for API exception
        mock_env_get.return_value = 'test_api_key'

        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance

        # Make the API call raise an exception
        mock_client_instance.chat.completions.create.side_effect = Exception("API Error")

        # Act & Verify
        with self.assertRaises(Exception) as context:
            import main

        self.assertEqual(str(context.exception), "API Error")

        mock_print.assert_not_called()

if __name__ == '__main__':
    unittest.main()
