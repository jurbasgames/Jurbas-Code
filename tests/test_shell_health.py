import pytest
from jurbas_code.tools import ShellHealth, shell_health

@pytest.fixture(autouse=True)
def reset_health():
    """Reset the ShellHealth state before and after each test."""
    shell_health.reset()
    yield
    shell_health.reset()


def test_consecutive_failures_triggers_diagnostic():
    # 3 consecutive failures with "command not found"
    assert shell_health.record_result("foo", 127, "bash: foo: command not found") is None
    assert shell_health.record_result("bar", 127, "bash: bar: command not found") is None

    diag = shell_health.record_result("baz", 127, "bash: baz: command not found")
    assert diag is not None
    assert "Shell might be broken" in diag
    assert "3 consecutive known failures" in diag
    assert "command not found" in diag


def test_success_resets_counter():
    # 2 failures
    assert shell_health.record_result("foo", 127, "bash: foo: command not found") is None
    assert shell_health.record_result("bar", 127, "bash: bar: command not found") is None

    # 1 success
    assert shell_health.record_result("ls", 0, "") is None

    # Needs 3 more failures to trigger
    assert shell_health.record_result("foo", 127, "bash: foo: command not found") is None
    assert shell_health.record_result("bar", 127, "bash: bar: command not found") is None
    diag = shell_health.record_result("baz", 127, "bash: baz: command not found")
    assert diag is not None


def test_different_failure_signals():
    assert shell_health.record_result("foo", 1, "não tem distribuições instaladas no wsl") is None
    assert shell_health.record_result("bar", 1, "there are no distributions installed") is None

    diag = shell_health.record_result("baz", 1, "command is not recognized")
    assert diag is not None
    assert "not recognized" in diag
    assert "Shell might be broken" in diag


def test_unknown_error_does_not_trigger():
    # Non-zero exit but no known signals
    assert shell_health.record_result("foo", 1, "Permission denied") is None
    assert shell_health.record_result("bar", 1, "Segmentation fault") is None
    assert shell_health.record_result("baz", 1, "") is None
    assert shell_health.is_broken() is False


def test_unknown_error_resets_counter():
    # 2 failures
    assert shell_health.record_result("foo", 127, "bash: foo: command not found") is None
    assert shell_health.record_result("bar", 127, "bash: bar: command not found") is None

    # 1 unknown error should reset the counter to prevent false positives
    assert shell_health.record_result("baz", 1, "Permission denied") is None

    # Now needs 3 more failures to trigger
    assert shell_health.record_result("foo", 127, "bash: foo: command not found") is None
    assert shell_health.record_result("bar", 127, "bash: bar: command not found") is None
    diag = shell_health.record_result("baz", 127, "bash: baz: command not found")
    assert diag is not None
