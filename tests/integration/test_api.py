from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.api.dependencies import get_db_session, get_agent_engine
from agent_api.main import create_app
from agent_api.models.agent import Message, ToolCall, ToolCallFunction
from agent_api.models.domain import Order, OrderStatus, User


@pytest.fixture
def test_app():
    """Create a fresh app instance for E2E tests."""
    return create_app()


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides a test client for the FastAPI app."""
    transport = httpx.ASGITransport(app=test_app)  # type: ignore
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_chat_endpoint_cancels_order_end_to_end(
        test_app,
        async_client: httpx.AsyncClient,
        real_db_session: AsyncSession,
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
    await real_db_session.commit()

    # 2. Arrange: Override the FastAPI database dependency to use the
    #    transactional test session (rolled back at teardown).
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield real_db_session

    test_app.dependency_overrides[get_db_session] = override_get_db_session

    # Provide required app.state attributes that the middleware needs
    from unittest.mock import MagicMock
    from contextlib import asynccontextmanager

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def _fake_session():
        yield mock_session

    db_manager_mock = MagicMock()
    db_manager_mock.session = _fake_session
    test_app.state.db_manager = db_manager_mock
    test_app.state.http_client = AsyncMock()

    # 3. Arrange: Mock the LLM to simulate a Reason -> Act -> Observe loop
    mock_llm_chat = AsyncMock()
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

    # 6. Assert: Verify the side-effect in the actual database
    await real_db_session.refresh(order)
    assert order.status == OrderStatus.CANCELLED

    # Teardown
    test_app.dependency_overrides.clear()
