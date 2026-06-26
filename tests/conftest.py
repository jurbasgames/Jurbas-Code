import os

# Disable TUI during tests by default to prevent tests from hanging on Textual app execution.
# Tests that explicitly test the TUI can override this (e.g. by passing --tui or patching JURBAS_TUI="1").
os.environ["JURBAS_TUI"] = "0"
