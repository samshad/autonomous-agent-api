from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Tool:
    """Represents an executable action available to the LLM."""

    name: str
    description: str
    func: Callable[..., Awaitable[str]]
    args_schema: type[BaseModel]

    def get_tool_schema(self) -> dict[str, Any]:
        """
        Dynamically generates an OpenAI/Ollama compliant function schema
        using Pydantic's internal JSON schema builder.
        """
        schema = self.args_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        }


class ToolRegistry:
    """
    Central registry for LLM tools using the Open/Closed Principle.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, args_schema: type[BaseModel], name: str | None = None) -> Callable[..., Any]:
        """
        Decorator to register a Python function as an LLM tool.
        Requires a Pydantic model for argument validation and a thorough docstring.
        """

        def decorator(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
            tool_name = name or func.__name__
            description = inspect.getdoc(func)

            if not description:
                logger.error("tool_registration_missing_docstring", tool_name=tool_name)
                raise ValueError(f"Tool function '{tool_name}' must have a docstring.")

            self._tools[tool_name] = Tool(
                name=tool_name,
                description=description.strip().split("\n\n")[0],
                func=func,
                args_schema=args_schema,
            )
            logger.debug("tool_registered", tool_name=tool_name)

            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> str:
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def get_tool(self, name: str) -> Tool | None:
        """Retrieves a registered tool by its name."""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Returns the fully compiled list of JSON schemas to pass into the LLM payload."""
        return [tool.get_tool_schema() for tool in self._tools.values()]


registry = ToolRegistry()
