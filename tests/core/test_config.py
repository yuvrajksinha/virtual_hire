"""Tests for app.core.config (VHIRE-5)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://sift:sift@localhost:5432/sift",
    "QDRANT_URL": "https://test-cluster.qdrant.io",
    "REDIS_URL": "redis://localhost:6379/0",
}


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """get_settings is process-cached; clear it so tests don't leak state."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_get_settings_returns_settings_with_required_values(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)

    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.database_url == REQUIRED_ENV["DATABASE_URL"]
    assert settings.qdrant_url == REQUIRED_ENV["QDRANT_URL"]
    assert settings.redis_url == REQUIRED_ENV["REDIS_URL"]


def test_get_settings_is_cached_per_process(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)

    first = get_settings()
    second = get_settings()

    assert first is second


def test_settings_missing_required_field_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_optional_fields_default_without_env(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)
    for key in (
        "QDRANT_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "S3_BUCKET_NAME",
        "AUTH_JWKS_URL",
        "AUTH_JWT_ISSUER",
        "AUTH_JWT_AUDIENCE",
        "MAGIC_LINK_SECRET_KEY",
        "MAGIC_LINK_TTL_SECONDS",
        "ANTHROPIC_API_KEY",
        "VOYAGE_API_KEY",
        "EMAIL_PROVIDER_API_KEY",
        "ENVIRONMENT",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.qdrant_api_key == ""
    assert settings.aws_region == "us-east-1"
    assert settings.s3_bucket_name == "sift-resumes-dev"
    assert settings.auth_jwks_url == ""
    assert settings.magic_link_secret_key == ""
    assert settings.magic_link_ttl_seconds == 900
    assert settings.anthropic_api_key == ""
