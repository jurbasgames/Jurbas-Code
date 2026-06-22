from types import SimpleNamespace
from unittest.mock import patch

import pytest

import jurbas.providers as jurbas_providers
import jurbas_code.providers as jurbas_code_providers


class FakeModels:
    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error

    def list(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self, model_ids=None, error=None):
        self.models = FakeModels(
            [SimpleNamespace(id=model_id) for model_id in model_ids or []],
            error=error,
        )


@pytest.mark.parametrize("providers", [jurbas_providers, jurbas_code_providers])
@pytest.mark.parametrize(
    ("provider", "env_var"),
    [("claude", "CLAUDE_MODEL"), ("deepseek", "DEEPSEEK_MODEL")],
)
def test_provider_model_env_wins_over_llm_model(providers, provider, env_var):
    client = FakeClient(["listed-model"])

    with patch.dict(
        "os.environ",
        {env_var: "provider-specific-model", "LLM_MODEL": "generic-model"},
        clear=True,
    ):
        assert providers.resolve_provider_model(provider, client) == "provider-specific-model"


@pytest.mark.parametrize("providers", [jurbas_providers, jurbas_code_providers])
def test_llm_model_used_when_provider_env_is_missing(providers):
    client = FakeClient(["listed-model"])

    with patch.dict("os.environ", {"LLM_MODEL": "generic-model"}, clear=True):
        assert providers.resolve_provider_model("claude", client) == "generic-model"


@pytest.mark.parametrize("providers", [jurbas_providers, jurbas_code_providers])
@pytest.mark.parametrize("provider", ["claude", "deepseek"])
def test_model_list_success_uses_listed_model(providers, provider):
    client = FakeClient(["listed-model"])

    with patch.dict("os.environ", {}, clear=True):
        assert providers.resolve_provider_model(provider, client) == "listed-model"


@pytest.mark.parametrize("providers", [jurbas_providers, jurbas_code_providers])
@pytest.mark.parametrize(
    ("provider", "default_name"),
    [
        ("claude", "DEFAULT_CLAUDE_MODEL"),
        ("deepseek", "DEFAULT_DEEPSEEK_MODEL"),
    ],
)
def test_model_list_failure_falls_back_to_known_default(providers, provider, default_name):
    client = FakeClient(error=RuntimeError("offline"))

    with patch.dict("os.environ", {}, clear=True):
        assert providers.resolve_provider_model(provider, client) == getattr(providers, default_name)
