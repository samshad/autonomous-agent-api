import pytest
from pydantic import ValidationError

from agent_api.core.config import Settings


def test_settings_validation_fails_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures the app cannot start if the critical database_url is missing."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "database_url" in str(exc_info.value)


def test_settings_loads_correctly_with_valid_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures Settings populates correctly given valid environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/db")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5")

    s = Settings(_env_file=None)

    assert s.database_url == "postgresql+asyncpg://test:test@localhost/db"
    assert s.llm_model == "qwen2.5"
    assert s.environment == "development"


def test_settings_defaults_are_sensible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures every default has a sane production-safe value."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/db")

    s = Settings(_env_file=None)

    assert s.debug is False
    assert s.pool_size == 5
    assert s.pool_max_overflow == 10
    assert s.pool_recycle_seconds == 300
    assert s.llm_timeout == 120.0
    assert s.max_react_iterations == 10
    assert s.cors_allowed_origins == ["*"]
    assert s.log_level == "INFO"
    assert s.max_prompt_length == 2000
    assert s.betterstack_source_token is None
    assert s.llm_api_key is None
    assert s.api_v1_prefix == "/api/v1"


def test_settings_overrides_all_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures every field can be overridden via environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/db")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("POOL_SIZE", "20")
    monkeypatch.setenv("POOL_MAX_OVERFLOW", "30")
    monkeypatch.setenv("POOL_RECYCLE_SECONDS", "600")
    monkeypatch.setenv("LLM_TIMEOUT", "60.0")
    monkeypatch.setenv("MAX_REACT_ITERATIONS", "5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MAX_PROMPT_LENGTH", "500")
    monkeypatch.setenv("LLM_API_KEY", "sk-secret")

    s = Settings(_env_file=None)

    assert s.environment == "production"
    assert s.debug is True
    assert s.pool_size == 20
    assert s.pool_max_overflow == 30
    assert s.pool_recycle_seconds == 600
    assert s.llm_timeout == 60.0
    assert s.max_react_iterations == 5
    assert s.log_level == "DEBUG"
    assert s.max_prompt_length == 500
    assert s.llm_api_key.get_secret_value() == "sk-secret"


def test_settings_extra_env_vars_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensures unknown env vars don't crash Settings (extra='ignore')."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/db")
    monkeypatch.setenv("TOTALLY_UNKNOWN_VAR", "should_not_crash")

    s = Settings(_env_file=None)
    assert s.database_url == "postgresql+asyncpg://x:x@localhost/db"
