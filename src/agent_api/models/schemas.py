from __future__ import annotations

from pydantic import BaseModel, Field

from agent_api.core.config import settings


class ChatRequest(BaseModel):
    """Payload sent by the frontend client."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_prompt_length,
        description="The user's natural language request.",
    )
    # In a real app, user_id would come from a JWT token in the Authorization header.
    # For this MVP, we pass it in the body to simulate an authenticated session.
    user_id: int | None = Field(default=None, description="The authenticated user's ID.")


class ChatResponse(BaseModel):
    """Payload returned to the frontend client."""

    response: str = Field(..., description="The natural language response from the AI.")
    request_id: str | None = Field(
        default=None,
        description="Correlation ID for this request (also in X-Request-ID header).",
    )
