import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add the root directory to sys.path so main.py can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import main

class MockDelta:
    def __init__(self, role=None, content=None, reasoning_content=None, tool_calls=None):
        self.role = role
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls

class MockChoice:
    def __init__(self, delta, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason

class MockChunk:
    def __init__(self, choices):
        self.choices = choices

def test_main_streaming_success(capsys, monkeypatch):
    # Mock user input to send "Hello", then "exit"
    inputs = ["Hello", "exit"]
    monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

    # Mock the API stream
    mock_chunks = [
        # Empty chunk (should be ignored safely)
        MockChunk([]),
        # Role chunk
        MockChunk([MockChoice(MockDelta(role="assistant"))]),
        # Reasoning chunk
        MockChunk([MockChoice(MockDelta(reasoning_content="Thinking..."))]),
        # Another reasoning chunk
        MockChunk([MockChoice(MockDelta(reasoning_content=" done."))]),
        # Content chunk
        MockChunk([MockChoice(MockDelta(content="Hello "))]),
        # Content chunk + finish_reason
        MockChunk([MockChoice(MockDelta(content="world!"), finish_reason="stop")]),
    ]

    mock_create = MagicMock(return_value=mock_chunks)

    with patch('main.OpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create = mock_create

        main.main()

    captured = capsys.readouterr()
    # Output should include the prompt and the streamed text
    assert "AI: Thinking... done.Hello world!" in captured.out

def test_main_streaming_interrupted(capsys, monkeypatch):
    # Mock user input to send "Hello", then "exit"
    inputs = ["Hello", "exit"]
    monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

    # Mock an API stream that raises an exception midway
    def faulty_stream():
        yield MockChunk([MockChoice(MockDelta(role="assistant"))])
        yield MockChunk([MockChoice(MockDelta(reasoning_content="Start thinking..."))])
        raise Exception("Connection lost")

    mock_create = MagicMock(return_value=faulty_stream())

    with patch('main.OpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create = mock_create

        main.main()

    captured = capsys.readouterr()
    assert "AI: Start thinking..." in captured.out
    assert "[Stream interrupted: Connection lost]" in captured.out
