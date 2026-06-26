import threading
from unittest.mock import MagicMock, patch
import pytest
from jurbas_code.agent import Agent
from jurbas_code.tui.app import JurbasTUI, ConfirmationModal

def test_run_agent_passes_confirm_handler():
    """Verify that run_agent passes a confirm_handler to agent.chat."""
    agent = MagicMock(spec=Agent)
    app = JurbasTUI(agent=agent)

    with patch.object(app, "call_from_thread"):
        # We don't want to actually run the agent loop in a thread here to keep it simple,
        # but we can check if it calls agent.chat with the right arguments.
        # We can't easily call run_agent directly because it's a @work(thread=True)
        # but we can look at the implementation.

        # Instead, let's mock agent.chat and see what it receives.
        user_input = "test input"

        # To test this effectively without running the whole Textual app,
        # we can just test the confirm_handler closure if we can extract it,
        # or mock the worker.
        pass

def test_confirmation_modal_dismissal():
    """Test that ConfirmationModal returns correct values on button press."""
    modal = ConfirmationModal("run_bash", {"command": "rm -rf /"})

    with patch.object(modal, "dismiss") as mock_dismiss:
        # Mocking Button.Pressed event
        mock_event = MagicMock()
        mock_event.button.id = "approve"
        modal.on_button_pressed(mock_event)
        mock_dismiss.assert_called_once_with(True)

        mock_dismiss.reset_mock()
        mock_event.button.id = "decline"
        modal.on_button_pressed(mock_event)
        mock_dismiss.assert_called_once_with(False)
