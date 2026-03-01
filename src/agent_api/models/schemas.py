from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Payload sent by the frontend client."""

    prompt: str = Field(..., description="The user's natural language request.")
    # In a real app, user_id would come from a JWT token in the Authorization header.
    # For this MVP, we pass it in the body to simulate an authenticated session.
    user_id: int | None = Field(default=None, description="The authenticated user's ID.")


class ChatResponse(BaseModel):
    """Payload returned to the frontend client."""

    response: str = Field(..., description="The natural language response from the AI.")
