from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_version() -> str:
    try:
        return _pkg_version("autonomous-agent-api")
    except PackageNotFoundError:
        return "0.0.0-dev"


class Settings(BaseSettings):
    """
    Core application settings mapped from environment variables.
    Fails fast on instantiation if required variables are missing.
    """

    # ── General ──────────────────────────────────────────────────────────
    project_name: str = "Autonomous AI Agent API"
    environment: str = Field(
        default="development",
        description="Runtime environment: development | staging | production",
    )
    debug: bool = False
    app_version: str = Field(
        default_factory=_get_version,
        description="Populated automatically from package metadata.",
    )

    api_v1_prefix: str = "/api/v1"

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = Field(
        ..., description="Async connection string (e.g., postgresql+asyncpg://...)"
    )
    pool_size: int = Field(default=5, description="SQLAlchemy engine pool size")
    pool_max_overflow: int = Field(default=10, description="Max connections above pool_size")
    pool_recycle_seconds: int = Field(
        default=300,
        description="Recycle connections after N seconds (Neon scale-to-zero safe)",
    )

    # ── LLM ──────────────────────────────────────────────────────────────
    llm_model: str = Field(default="qwen3:8b", description="Target model for Ollama or Cloud API")
    llm_base_url: str = Field(
        default="http://host.docker.internal:11434", description="Base URL for the LLM API"
    )
    llm_api_key: SecretStr | None = Field(
        default=None, description="Optional API key for cloud LLM providers"
    )
    llm_timeout: float = Field(
        default=120.0,
        description="HTTP timeout in seconds for LLM API calls",
    )

    max_react_iterations: int = Field(
        default=10,
        description="Maximum number of iterations for the ReAct loop to prevent infinite loops",
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_allowed_origins: list[str] = Field(
        default=["*"],
        description="Comma-separated allowed origins for CORS (set explicitly in production)",
    )

    # ── Logging ──────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Root log level")
    log_dir: str = Field(default="logs", description="Directory for rotating log files")
    log_max_bytes: int = Field(default=10_485_760, description="Max size per log file (bytes)")
    log_backup_count: int = Field(default=5, description="Number of rotated log backups")

    # ── Observability ────────────────────────────────────────────────────
    betterstack_source_token: str | None = Field(default=None)

    # ── Input Limits ─────────────────────────────────────────────────────
    max_prompt_length: int = Field(
        default=2000, description="Maximum character length for user prompts"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
