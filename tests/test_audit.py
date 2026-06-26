import pytest
import os
import json
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
