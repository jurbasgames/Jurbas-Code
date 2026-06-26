import os
import json
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Config:
    model_roles: Dict[str, str] = field(default_factory=lambda: {
        "embedding": "text-embedding-3-small",
        "chat": "claude-3-5-sonnet-latest"
    })
    index_paths: Dict[str, str] = field(default_factory=lambda: {
        "default": ".jurbas_index"
    })
    telegram_allowed_users: List[int] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        config = cls()

        # Load overrides from env if present
        model_roles_env = os.environ.get("JURBAS_MODEL_ROLES")
        if model_roles_env:
            try:
                overrides = json.loads(model_roles_env)
                if isinstance(overrides, dict):
                    config.model_roles.update(overrides)
            except json.JSONDecodeError:
                pass

        index_paths_env = os.environ.get("JURBAS_INDEX_PATHS")
        if index_paths_env:
            try:
                overrides = json.loads(index_paths_env)
                if isinstance(overrides, dict):
                    config.index_paths.update(overrides)
            except json.JSONDecodeError:
                pass

        telegram_allowed_users_env = os.environ.get("JURBAS_TELEGRAM_ALLOWED_USERS")
        if telegram_allowed_users_env:
            try:
                allowed = json.loads(telegram_allowed_users_env)
                if isinstance(allowed, list):
                    config.telegram_allowed_users = [int(u) for u in allowed]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        return config

def get_config() -> Config:
    return Config.from_env()
