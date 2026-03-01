from __future__ import annotations

from typing import Any, Protocol

import httpx
import structlog

from agent_api.models.agent import Message

logger = structlog.get_logger(__name__)


class LLMClient(Protocol):
    """Dependency Inversion interface for AI providers."""

    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Message: ...


class OllamaClient:
    """Concrete implementation for local Ollama.

    Accepts an *external* ``httpx.AsyncClient`` so the connection pool
    is managed by the application lifespan, not per-request.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
        model: str,
    ) -> None:
        self._http = http_client
        self.base_url = base_url.rstrip("/") + "/api"
        self.model = model

    async def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> Message:
        """Sends conversation history and available tools to the LLM."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            response = await self._http.post(f"{self.base_url}/chat", json=payload)
            response.raise_for_status()
            data = response.json()

            logger.debug("llm_response", data=data)

            return Message(**data.get("message", {}))
        except httpx.HTTPError as e:
            logger.error("llm_network_error", error=str(e))
            raise RuntimeError(f"Failed to communicate with LLM: {e}")
