import os
import json
from unittest import mock

from jurbas_code.config import Config, get_config


def test_config_defaults():
    config = Config.from_env()
    assert config.model_roles["embedding"] == "text-embedding-3-small"
    assert config.model_roles["chat"] == "claude-3-5-sonnet-latest"
    assert config.index_paths["default"] == ".jurbas_index"


def test_config_env_overrides():
    env = {
        "JURBAS_MODEL_ROLES": json.dumps(
            {"embedding": "custom-embedding", "new_role": "gpt-4"}
        ),
        "JURBAS_INDEX_PATHS": json.dumps(
            {"default": "/tmp/custom_index", "secondary": ".other_index"}
        ),
    }
    with mock.patch.dict(os.environ, env):
        config = Config.from_env()
        assert config.model_roles["embedding"] == "custom-embedding"
        assert (
            config.model_roles["chat"] == "claude-3-5-sonnet-latest"
        )  # Preserved default
        assert config.model_roles["new_role"] == "gpt-4"  # Added new role
        assert config.index_paths["default"] == "/tmp/custom_index"
        assert config.index_paths["secondary"] == ".other_index"  # Added new path


def test_get_config():
    # Should just run without issues and return an instance
    config = get_config()
    assert isinstance(config, Config)


def test_invalid_json_env_ignored():
    env = {"JURBAS_MODEL_ROLES": "invalid_json"}
    with mock.patch.dict(os.environ, env):
        config = Config.from_env()
        assert config.model_roles["embedding"] == "text-embedding-3-small"


def test_non_dict_json_env_ignored():
    env = {"JURBAS_MODEL_ROLES": json.dumps(["not", "a", "dict"])}
    with mock.patch.dict(os.environ, env):
        config = Config.from_env()
        assert config.model_roles["embedding"] == "text-embedding-3-small"
