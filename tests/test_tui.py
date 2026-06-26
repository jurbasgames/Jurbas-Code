import os
import sys
from unittest.mock import patch, MagicMock
import pytest

# Skip all tests in this file if textual is not installed
textual = pytest.importorskip("textual")

from main import main

def test_tui_flag_checks_imports():
    """Test that running with --tui tries to load the TUI and checks dependencies."""

    # Mock sys.exit to prevent the test from dying if it errors out
    with patch("sys.exit") as mock_exit:
        # Mock sys.argv
        with patch.object(sys, "argv", ["main.py", "--tui"]):
            # Also mock the client initialization to avoid actual API dependency
            with patch("main.get_client", return_value=MagicMock()):
                # If TUI is not installed properly or mock environment fails,
                # it should either exit with code 1 (ImportError path) or run the app.

                # Mock the app.run to not actually start the terminal UI which would block
                with patch("jurbas_code.tui.app.JurbasTUI.run") as mock_run:
                    main(["--tui"])

                    # Ensure run was called
                    mock_run.assert_called_once()

def test_tui_env_var_works():
    """Test that JURBAS_TUI=1 env var also triggers the TUI."""
    with patch.dict(os.environ, {"JURBAS_TUI": "1", "LLM_PROVIDER": "claude"}):
        with patch("main.get_client", return_value=MagicMock()):
            with patch("jurbas_code.tui.app.JurbasTUI.run") as mock_run:
                main([])
                mock_run.assert_called_once()

def test_non_tui_runs_cli(monkeypatch):
    """Test that not using --tui runs the standard CLI."""
    # We mock input to raise EOFError immediately to break the while loop cleanly
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=EOFError))

    with patch("main.get_client", return_value=MagicMock()):
        with patch("jurbas_code.tui.app.JurbasTUI") as mock_tui:
            main([])

            # Ensure TUI was NOT instantiated
            mock_tui.assert_not_called()
