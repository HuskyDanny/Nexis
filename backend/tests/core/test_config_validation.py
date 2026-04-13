"""Tests for production config validation.

Each test creates a fresh Settings instance with _env_file=None to
isolate from .env.base/.env on disk. Never imports or mutates the
global singleton.
"""

import pytest

from src.core.config import Settings

# Shared valid-production kwargs — all secrets present, env file disabled
_PROD_BASE = {
    "_env_file": None,
    "environment": "production",
    "neo4j_password": "real-password",
    "secret_key": "a-strong-production-secret",
    "siliconflow_api_key": "sk-prod-key-1234",
}


def _settings(**overrides) -> Settings:
    """Create a Settings instance isolated from .env files."""
    return Settings(_env_file=None, **overrides)


class TestProductionValidation:
    """Non-development environments must provide all required secrets."""

    def test_empty_neo4j_password_raises(self):
        with pytest.raises(ValueError, match="neo4j_password"):
            Settings(**{**_PROD_BASE, "neo4j_password": ""})

    def test_empty_secret_key_raises(self):
        with pytest.raises(ValueError, match="secret_key"):
            Settings(**{**_PROD_BASE, "secret_key": ""})

    def test_dev_in_secret_key_raises(self):
        with pytest.raises(ValueError, match="secret_key"):
            Settings(**{**_PROD_BASE, "secret_key": "dev-leftover-key"})

    def test_empty_siliconflow_api_key_raises(self):
        with pytest.raises(ValueError, match="siliconflow_api_key"):
            Settings(**{**_PROD_BASE, "siliconflow_api_key": ""})

    def test_multiple_missing_lists_all(self):
        with pytest.raises(ValueError, match="neo4j_password") as exc_info:
            _settings(environment="production")
        msg = str(exc_info.value)
        assert "secret_key" in msg
        assert "siliconflow_api_key" in msg

    def test_all_secrets_provided_passes(self):
        s = Settings(**_PROD_BASE)
        assert s.environment == "production"
        assert s.neo4j_password == "real-password"


class TestDevelopmentValidation:
    """Development mode must accept empty/default secrets for backward compat."""

    def test_empty_secrets_allowed(self):
        s = _settings(environment="development")
        assert s.environment == "development"
        assert s.neo4j_password == ""

    def test_dev_default_secret_key_allowed(self):
        s = _settings(environment="development", secret_key="dev-test-key")
        assert s.secret_key == "dev-test-key"


class TestNewConfigFields:
    """Verify new fields have correct defaults."""

    def test_log_format_default(self):
        s = _settings(environment="development")
        assert s.log_format == "text"

    def test_log_format_json(self):
        s = _settings(environment="development", log_format="json")
        assert s.log_format == "json"

    def test_alpha_vantage_api_key_default(self):
        s = _settings(environment="development")
        assert s.alpha_vantage_api_key == ""
