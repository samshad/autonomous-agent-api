from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

Role = Literal["system", "user", "assistant", "tool"]


class ToolCallFunction(BaseModel):
    name: str
    arguments: dict[str, Any]


class ToolCall(BaseModel):
    # Ollama doesn't always provide an ID, whereas OpenAI does.
    id: str = "call_default"
    type: Literal["function"] = "function"
    function: ToolCallFunction


class Message(BaseModel):
    """Represents a single message in the LLM conversation history."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    # Used only when role == "tool" to map the result back to the specific call
    tool_call_id: str | None = None
