"""Tests for runtime configuration."""

import pytest  # pylint: disable=import-error

from app import config
from app.config import Settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Ensure each test resolves settings freshly."""
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_default_model_when_unset(monkeypatch):
    """Falls back to the built-in default when PLEXMUSE_MODEL is unset."""
    monkeypatch.delenv("PLEXMUSE_MODEL", raising=False)
    monkeypatch.delenv("PLEXMUSE_MODELS", raising=False)
    settings = Settings()
    assert settings.default_model == "gpt-4"
    assert settings.available_models == ["gpt-4"]


def test_configured_default_model(monkeypatch):
    """PLEXMUSE_MODEL overrides the default model."""
    monkeypatch.setenv("PLEXMUSE_MODEL", "anthropic/claude-3-5-sonnet-latest")
    monkeypatch.delenv("PLEXMUSE_MODELS", raising=False)
    settings = Settings()
    assert settings.default_model == "anthropic/claude-3-5-sonnet-latest"
    assert settings.available_models == ["anthropic/claude-3-5-sonnet-latest"]


def test_available_models_list_with_default_first(monkeypatch):
    """PLEXMUSE_MODELS is parsed and the default model is listed first without duplication."""
    monkeypatch.setenv("PLEXMUSE_MODEL", "gpt-4o")
    monkeypatch.setenv("PLEXMUSE_MODELS", "gpt-4o, gpt-3.5-turbo , anthropic/claude-3-5-sonnet-latest")
    settings = Settings()
    assert settings.available_models == [
        "gpt-4o",
        "gpt-3.5-turbo",
        "anthropic/claude-3-5-sonnet-latest",
    ]


def test_default_prepended_when_not_in_models_list(monkeypatch):
    """The default model is always selectable even if omitted from PLEXMUSE_MODELS."""
    monkeypatch.setenv("PLEXMUSE_MODEL", "gpt-4o")
    monkeypatch.setenv("PLEXMUSE_MODELS", "gpt-3.5-turbo")
    settings = Settings()
    assert settings.available_models == ["gpt-4o", "gpt-3.5-turbo"]
