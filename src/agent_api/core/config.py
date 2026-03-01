from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Core application settings mapped from environment variables.
    Fails fast on instantiation if required variables are missing.
    """

    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    database_url: str = Field(
        ..., description="Async connection string (e.g., postgresql+asyncpg://...)"
    )

    llm_model: str = Field(default="llama3.1", description="Target model for Ollama or Cloud API")
    llm_base_url: str = Field(
        default="http://localhost:11434/api", description="Base URL for the LLM API"
    )
    llm_api_key: SecretStr | None = Field(
        default=None, description="Optional API key for cloud LLM providers"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
