from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.api.dependencies import get_db_session
from agent_api.main import app
from agent_api.models.agent import Message, ToolCall, ToolCallFunction
from agent_api.models.domain import Order, OrderStatus, User


@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides a test client for the FastAPI app."""
    # We use ASGI transport to test the app directly without needing to spin up Uvicorn
    transport = httpx.ASGITransport(app=app)  # type: ignore
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_chat_endpoint_cancels_order_end_to_end(
        async_client: httpx.AsyncClient,
        real_db_session: AsyncSession
) -> None:
    """
    Proves that sending a natural language request via HTTP successfully executes
    the ReAct loop, updates the real Postgres database, and returns a response.
    """
    # 1. Arrange: Seed the isolated test database
    user = User(email="api_e2e@example.com", full_name="API Tester")
    real_db_session.add(user)
    await real_db_session.flush()

    order = Order(user_id=user.id, status=OrderStatus.PENDING)
    real_db_session.add(order)
    await real_db_session.flush()
    # Explicitly commit to simulate data existing before the request starts
    await real_db_session.commit()

    # 2. Arrange: Override the FastAPI database dependency
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield real_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    # 3. Arrange: Mock the LLM to simulate a Reason -> Act -> Observe loop deterministically
    mock_llm_chat = AsyncMock()
    # First LLM call: The AI decides it needs to use the cancel_order_tool
    msg1 = Message(
        role="assistant",
        tool_calls=[
            ToolCall(
                id="call_mocked",
                type="function",
                function=ToolCallFunction(
                    name="cancel_order_tool",
                    arguments={"order_id": order.id}
                )
            )
        ]
    )
    # Second LLM call: The AI reads the tool's success string and replies to the user
    msg2 = Message(
        role="assistant",
        content=f"Success! I have cancelled your order #{order.id}."
    )
    mock_llm_chat.side_effect = [msg1, msg2]

    # 4. Act: Send the HTTP POST request to the API
    payload = {"prompt": f"Cancel my order #{order.id}", "user_id": user.id}

    with patch("agent_api.agent.llm_client.OllamaClient.chat", mock_llm_chat):
        response = await async_client.post("/api/v1/chat", json=payload)

    # 5. Assert: Check the HTTP boundary
    assert response.status_code == 200
    data = response.json()
    assert "Success! I have cancelled your order" in data["response"]

    # 6. Assert: Verify the side-effect in the actual database via SQLAlchemy
    await real_db_session.refresh(order)
    assert order.status == OrderStatus.CANCELLED

    # Teardown: Remove the dependency override so other tests aren't affected
    app.dependency_overrides.clear()
