import pytest
import os
import json
import logging
from jurbas_code.audit import AuditLogger

@pytest.fixture
def temp_audit_file(tmp_path):
    return str(tmp_path / "audit.jsonl")

def test_audit_logger_chain(temp_audit_file):
    logger = AuditLogger(filepath=temp_audit_file)

    # First action
    logger.log_action("test_action_1", {"key": "value1"})

    with open(temp_audit_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry1 = json.loads(lines[0])
        assert entry1["previous_hash"] is None
        assert entry1["action_type"] == "test_action_1"

    hash1 = logger.last_hash

    # Second action
    logger.log_action("test_action_2", {"key": "value2"})

    with open(temp_audit_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2
        entry2 = json.loads(lines[1])
        assert entry2["previous_hash"] == hash1
        assert entry2["action_type"] == "test_action_2"

def test_audit_logger_resumes_chain(temp_audit_file):
    logger1 = AuditLogger(filepath=temp_audit_file)
    logger1.log_action("init_action", {"test": True})
    first_hash = logger1.last_hash

    logger2 = AuditLogger(filepath=temp_audit_file)
    assert logger2.last_hash == first_hash

    logger2.log_action("next_action", {"test": False})

    with open(temp_audit_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2
        entry2 = json.loads(lines[1])
        assert entry2["previous_hash"] == first_hash

def test_audit_logger_corrupted_file_logs_warning(temp_audit_file, caplog):
    # Setup: Create a valid audit file then corrupt it
    logger = AuditLogger(filepath=temp_audit_file)
    logger.log_action("valid_action", {"key": "value"})

    with open(temp_audit_file, "w") as f:
        f.write("invalid json line\n")

    # Action: Initialize new logger with corrupted file
    with caplog.at_level(logging.WARNING):
        new_logger = AuditLogger(filepath=temp_audit_file)

    # Assert
    assert new_logger.last_hash is None
    assert any("Failed to parse last audit entry" in record.message for record in caplog.records)
    assert any(record.levelno == logging.WARNING for record in caplog.records)

def test_audit_logger_strict_mode_raises_on_corruption(temp_audit_file, monkeypatch):
    # Setup: Create a valid audit file then corrupt it
    logger = AuditLogger(filepath=temp_audit_file)
    logger.log_action("valid_action", {"key": "value"})

    with open(temp_audit_file, "w") as f:
        f.write("invalid json line\n")

    # Enable strict mode
    monkeypatch.setenv("JURBAS_STRICT_AUDIT", "1")

    # Action & Assert: Initialize new logger in strict mode should raise
    with pytest.raises(RuntimeError, match="Failed to parse last audit entry"):
        AuditLogger(filepath=temp_audit_file)

def test_audit_logger_strict_mode_raises_on_io_error(temp_audit_file, monkeypatch):
    # Setup: Create a directory where the file should be to cause an IsADirectoryError (IOError)
    os.makedirs(temp_audit_file, exist_ok=True)

    # Enable strict mode
    monkeypatch.setenv("JURBAS_STRICT_AUDIT", "1")

    # Action & Assert: Initialize new logger in strict mode should raise
    with pytest.raises(RuntimeError, match="Failed to read last audit hash"):
        AuditLogger(filepath=temp_audit_file)
