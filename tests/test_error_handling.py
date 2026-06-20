import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from unittest.mock import patch, MagicMock
from openai import AuthenticationError, APIError, RateLimitError, APITimeoutError
import main

@patch('builtins.input', side_effect=['hello', 'exit'])
@patch('main.OpenAI')
def test_authentication_error(mock_openai, mock_input, capsys):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.request.url = "http://fake"
    mock_client.chat.completions.create.side_effect = AuthenticationError("Auth error", response=mock_response, body=None)

    main.main()

    captured = capsys.readouterr()
    assert "AI: Authentication Error:" in captured.out

@patch('builtins.input', side_effect=['hello', 'exit'])
@patch('main.OpenAI')
def test_rate_limit_error(mock_openai, mock_input, capsys):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.request.url = "http://fake"
    mock_client.chat.completions.create.side_effect = RateLimitError("Rate limit error", response=mock_response, body=None)

    main.main()

    captured = capsys.readouterr()
    assert "AI: Rate Limit Error:" in captured.out

@patch('builtins.input', side_effect=['hello', 'exit'])
@patch('main.OpenAI')
def test_timeout_error(mock_openai, mock_input, capsys):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_request = MagicMock()
    mock_client.chat.completions.create.side_effect = APITimeoutError(request=mock_request)

    main.main()

    captured = capsys.readouterr()
    assert "AI: Timeout Error:" in captured.out

@patch('builtins.input', side_effect=['hello', 'exit'])
@patch('main.OpenAI')
def test_api_error(mock_openai, mock_input, capsys):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_request = MagicMock()
    mock_request.url = "http://fake"
    mock_client.chat.completions.create.side_effect = APIError("API error", request=mock_request, body=None)

    main.main()

    captured = capsys.readouterr()
    assert "AI: API Error:" in captured.out

@patch('builtins.input', side_effect=['hello', 'exit'])
@patch('main.OpenAI')
def test_unexpected_error(mock_openai, mock_input, capsys):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_client.chat.completions.create.side_effect = Exception("Unexpected")

    main.main()

    captured = capsys.readouterr()
    assert "AI: Unexpected Error:" in captured.out

@patch('builtins.input', side_effect=['hello', 'exit'])
@patch('main.OpenAI')
def test_empty_choices(mock_openai, mock_input, capsys):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices = []
    mock_client.chat.completions.create.return_value = mock_response

    main.main()

    captured = capsys.readouterr()
    assert "AI: Error: No response choices returned from the API." in captured.out
