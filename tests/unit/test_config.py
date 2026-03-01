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
    # Arrange
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/db")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5")

    # Act
    settings = Settings(_env_file=None)

    # Assert
    assert settings.database_url == "postgresql+asyncpg://test:test@localhost/db"
    assert settings.llm_model == "qwen2.5"
    assert settings.environment == "development"
