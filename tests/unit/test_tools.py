from unittest.mock import AsyncMock
from datetime import UTC, datetime

import pytest

from agent_api.agent.tools import cancel_order_tool, list_orders_tool, get_order_details_tool
from agent_api.core.exceptions import BusinessRuleError, EntityNotFoundError, OwnershipError
from agent_api.models.domain import Order, OrderStatus
from agent_api.services.commerce import CommerceService


@pytest.fixture
def mock_service() -> AsyncMock:
    return AsyncMock(spec=CommerceService)


@pytest.mark.asyncio
async def test_cancel_order_tool_success(mock_service: AsyncMock) -> None:
    """Ensures a successful cancellation returns a formatted success string."""
    mock_order = Order(id=101, status=OrderStatus.CANCELLED)
    mock_service.cancel_order.return_value = mock_order

    result = await cancel_order_tool(service=mock_service, order_id=101)

    assert "Success" in result
    assert "Order #101" in result
    assert "cancelled" in result


@pytest.mark.asyncio
async def test_cancel_order_tool_catches_domain_error(mock_service: AsyncMock) -> None:
    """Ensures domain exceptions are caught and returned as readable strings for the LLM."""
    # Simulate the service raising a business rule error (e.g., already shipped)
    mock_service.cancel_order.side_effect = BusinessRuleError("Cannot cancel order #101: already 'shipped'.")

    result = await cancel_order_tool(service=mock_service, order_id=101)

    # The exception should NOT bubble up. It should be returned as a string.
    assert "Action Failed" in result
    assert "already 'shipped'" in result


@pytest.mark.asyncio
async def test_list_orders_tool_success(mock_service: AsyncMock) -> None:
    """Ensures listed orders are formatted into a readable string list."""
    mock_service.list_orders.return_value = {
        "count": 1,
        "orders": [
            {
                "order_id": 99,
                "status": "pending",
                "created_at": "2026-03-01T12:00:00Z",
                "updated_at": "2026-03-01T12:00:00Z",
            }
        ]
    }

    result = await list_orders_tool(service=mock_service, user_id=5)

    assert "Found 1 orders" in result
    assert "- Order #99" in result
    assert "Status: pending" in result


@pytest.mark.asyncio
async def test_get_order_details_tool_success(mock_service: AsyncMock) -> None:
    """Ensures fetching a single order formats the details string correctly."""
    mock_order = Order(id=55, status=OrderStatus.PROCESSING)
    mock_order.created_at = datetime.now(UTC)
    mock_order.updated_at = datetime.now(UTC)
    mock_service.get_order_details.return_value = mock_order

    result = await get_order_details_tool(service=mock_service, order_id=55)

    assert "Order #55 Details:" in result
    assert "Status: 'processing'" in result


@pytest.mark.asyncio
async def test_get_order_details_tool_not_found(mock_service: AsyncMock) -> None:
    """Ensures a missing order exception is caught and returned as a string."""
    mock_service.get_order_details.side_effect = EntityNotFoundError("Order #999 could not be found.")

    result = await get_order_details_tool(service=mock_service, order_id=999)

    assert "Action Failed" in result
    assert "could not be found" in result


@pytest.mark.asyncio
async def test_get_order_details_tool_ownership_error(mock_service: AsyncMock) -> None:
    """Ensures attempting to view another user's order returns a safe failure string."""
    # Simulate the service raising an OwnershipError (which extends AgentAPIError)
    mock_service.get_order_details.side_effect = OwnershipError("Order #55 could not be found.")

    # Act
    result = await get_order_details_tool(service=mock_service, order_id=55, user_id=999)

    # Assert
    assert "Action Failed" in result
    assert "could not be found" in result
