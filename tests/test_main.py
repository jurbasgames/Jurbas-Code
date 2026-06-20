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

class MockFunction:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments

class MockToolCall:
    def __init__(self, index=0, id=None, type=None, function=None):
        self.index = index
        self.id = id
        self.type = type
        self.function = function

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


def test_safe_path_resolves_from_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    assert main.safe_path("main.py") == os.path.realpath(
        os.path.join(os.path.dirname(main.__file__), "main.py")
    )


def test_safe_path_converts_cross_drive_value_error(monkeypatch):
    def raise_value_error(_paths):
        raise ValueError("Paths don't have the same drive")

    monkeypatch.setattr(main.os.path, "commonpath", raise_value_error)

    with pytest.raises(PermissionError):
        main.safe_path("main.py")


def test_load_dotenv_and_read_file_blocks_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ALLOWED_BASE", os.path.realpath(tmp_path))
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    main.load_dotenv()

    assert os.environ["DEEPSEEK_API_KEY"] == "from-dotenv"
    assert "secret file" in main.read_file(".env")


def test_tool_call_finish_reason_without_tool_calls_breaks(capsys, monkeypatch):
    inputs = ["Hello", "exit"]
    monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))
    mock_chunks = [
        MockChunk([MockChoice(MockDelta(role="assistant"))]),
        MockChunk([MockChoice(MockDelta(content=""), finish_reason="tool_calls")]),
    ]
    mock_create = MagicMock(return_value=mock_chunks)

    with patch('main.OpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create = mock_create

        main.main()

    captured = capsys.readouterr()
    messages = mock_create.call_args.kwargs["messages"]
    assert mock_create.call_count == 1
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == ""
    assert "AI: " not in captured.out


def test_tool_only_step_does_not_print_empty_ai_prefix(capsys, monkeypatch):
    inputs = ["List", "exit"]
    monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))
    tool_call = MockToolCall(
        index=0,
        id="call_1",
        type="function",
        function=MockFunction(name="list_directory", arguments='{"dir_path": "."}'),
    )
    mock_create = MagicMock(side_effect=[
        [
            MockChunk([MockChoice(MockDelta(role="assistant"))]),
            MockChunk([MockChoice(MockDelta(tool_calls=[tool_call]), finish_reason="tool_calls")]),
        ],
        [
            MockChunk([MockChoice(MockDelta(role="assistant"))]),
            MockChunk([MockChoice(MockDelta(content="Done"), finish_reason="stop")]),
        ],
    ])

    with patch('main.OpenAI') as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create = mock_create

        main.main()

    captured = capsys.readouterr()
    assert "AI: \n" not in captured.out
    assert "  🔧 [list_directory]" in captured.out
    assert "AI: Done" in captured.out
