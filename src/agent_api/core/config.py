from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Core application settings mapped from environment variables.
    Fails fast on instantiation if required variables are missing.
    """

    project_name: str = "Autonomous AI Agent API"
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        ..., description="Async connection string (e.g., postgresql+asyncpg://...)"
    )

    llm_model: str = Field(default="qwen3:8b", description="Target model for Ollama or Cloud API")
    llm_base_url: str = Field(
        default="http://host.docker.internal:11434", description="Base URL for the LLM API"
    )
    llm_api_key: SecretStr | None = Field(
        default=None, description="Optional API key for cloud LLM providers"
    )

    max_react_iterations: int = Field(
        default=10,
        description="Maximum number of iterations for the ReAct loop to prevent infinite loops",
    )

    betterstack_source_token: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
