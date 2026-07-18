"""Tests for app.crew.models (VHIRE-2x / E6, extended by E17): the
OpenRouter model-configuration layer every crew agent role reads from.
"""

import os

import pytest

from app.core.config import get_settings
from app.crew.models import model_for_role


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_model_for_role_returns_the_configured_model_id():
    assert model_for_role("extraction") == get_settings().extraction_model
    assert model_for_role("judge") == get_settings().judge_model


def test_model_for_role_rejects_an_unknown_role():
    with pytest.raises(ValueError):
        model_for_role("not_a_real_role")


def test_model_for_role_sets_openrouter_api_key_env_var(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-value")
    get_settings.cache_clear()

    model_for_role("extraction")

    assert os.environ["OPENROUTER_API_KEY"] == "test-key-value"
