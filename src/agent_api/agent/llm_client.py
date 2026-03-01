from __future__ import annotations

from typing import Any, Protocol

import httpx
import structlog

from agent_api.core.config import settings
from agent_api.models.agent import Message

logger = structlog.get_logger(__name__)


class LLMClient(Protocol):
    """Dependency Inversion interface for AI providers."""

    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Message: ...


class OllamaClient:
    """Concrete implementation for local Ollama."""

    def __init__(
        self, base_url: str = settings.llm_base_url, model: str = settings.llm_model
    ) -> None:
        self.base_url = base_url
        self.model = model

    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Message:
        """Sends conversation history and available tools to the LLM."""
        payload = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(f"{self.base_url}/chat", json=payload)
                response.raise_for_status()
                data = response.json()

                logger.debug("llm_response", data=data)

                return Message(**data.get("message", {}))
            except httpx.HTTPError as e:
                logger.error("llm_network_error", error=str(e))
                raise RuntimeError(f"Failed to communicate with LLM: {e}")
