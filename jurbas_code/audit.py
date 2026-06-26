import json
import hashlib
import time
import os
import io
from typing import Any

class AuditLogger:
    def __init__(self, filepath: str = "audit.jsonl"):
        self.filepath = filepath
        self.last_hash = self._get_last_hash()

    def _get_last_hash(self) -> str | None:
        if not os.path.exists(self.filepath):
            return None

        try:
            last_line = None
            with io.open(self.filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        last_line = line.strip()
            if last_line:
                try:
                    data = json.loads(last_line)
                    return self._compute_hash(data)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        return None

    def _compute_hash(self, entry: dict[str, Any]) -> str:
        # Sort keys to ensure consistent JSON string representation for hashing
        serialized = json.dumps(entry, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def log_action(self, action_type: str, details: dict[str, Any]) -> None:
        entry = {
            "timestamp": time.time(),
            "action_type": action_type,
            "details": details,
            "previous_hash": self.last_hash
        }

        self.last_hash = self._compute_hash(entry)

        with io.open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

audit_logger = AuditLogger()
