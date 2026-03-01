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


# ──────────────────────────────────────────────────────────────────────────────
# cancel_order_tool
# ──────────────────────────────────────────────────────────────────────────────

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
async def test_cancel_order_tool_includes_timestamps(mock_service: AsyncMock) -> None:
    """Ensures the cancel response includes created_at and updated_at when available."""
    now = datetime.now(UTC)
    mock_order = Order(id=1, status=OrderStatus.CANCELLED)
    mock_order.created_at = now
    mock_order.updated_at = now
    mock_service.cancel_order.return_value = mock_order

    result = await cancel_order_tool(service=mock_service, order_id=1)

    assert "Originally created at:" in result
    assert "Last updated at:" in result
    assert now.isoformat() in result


@pytest.mark.asyncio
async def test_cancel_order_tool_handles_null_timestamps(mock_service: AsyncMock) -> None:
    """Ensures 'Unknown' is shown when timestamps are None."""
    mock_order = Order(id=1, status=OrderStatus.CANCELLED)
    mock_order.created_at = None
    mock_order.updated_at = None
    mock_service.cancel_order.return_value = mock_order

    result = await cancel_order_tool(service=mock_service, order_id=1)

    assert "Originally created at: Unknown" in result
    assert "Last updated at: Unknown" in result


@pytest.mark.asyncio
async def test_cancel_order_tool_catches_domain_error(mock_service: AsyncMock) -> None:
    """Ensures domain exceptions are caught and returned as readable strings for the LLM."""
    mock_service.cancel_order.side_effect = BusinessRuleError("Cannot cancel order #101: already 'shipped'.")

    result = await cancel_order_tool(service=mock_service, order_id=101)

    assert "Action Failed" in result
    assert "already 'shipped'" in result


@pytest.mark.asyncio
async def test_cancel_order_tool_catches_unexpected_exception(mock_service: AsyncMock) -> None:
    """Ensures non-domain exceptions are caught and returned as a safe generic string."""
    mock_service.cancel_order.side_effect = RuntimeError("DB connection lost")

    result = await cancel_order_tool(service=mock_service, order_id=1)

    assert "Action Failed" in result
    assert "unexpected system error" in result.lower()
    # Must NOT leak the raw error message to the LLM
    assert "DB connection lost" not in result


# ──────────────────────────────────────────────────────────────────────────────
# list_orders_tool
# ──────────────────────────────────────────────────────────────────────────────

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
                "updated_at": "2026-03-01T13:00:00Z",
            }
        ]
    }

    result = await list_orders_tool(service=mock_service, user_id=5)

    assert "Found 1 orders" in result
    assert "- Order #99" in result
    assert "Status: pending" in result
    assert "Created:" in result
    assert "Last Updated:" in result


@pytest.mark.asyncio
async def test_list_orders_tool_empty_history(mock_service: AsyncMock) -> None:
    """Ensures a helpful message when the user has no orders."""
    mock_service.list_orders.return_value = {"count": 0, "orders": []}

    result = await list_orders_tool(service=mock_service, user_id=42)

    assert "no order history" in result.lower()


@pytest.mark.asyncio
async def test_list_orders_tool_multiple_orders(mock_service: AsyncMock) -> None:
    """Ensures multiple orders are each represented in the output."""
    mock_service.list_orders.return_value = {
        "count": 3,
        "orders": [
            {"order_id": 1, "status": "pending", "created_at": "2026-01-01T00:00:00Z",
             "updated_at": "2026-01-01T00:00:00Z"},
            {"order_id": 2, "status": "shipped", "created_at": "2026-02-01T00:00:00Z",
             "updated_at": "2026-02-01T00:00:00Z"},
            {"order_id": 3, "status": "delivered", "created_at": "2026-03-01T00:00:00Z",
             "updated_at": "2026-03-01T00:00:00Z"},
        ]
    }

    result = await list_orders_tool(service=mock_service, user_id=1)

    assert "Found 3 orders" in result
    assert "Order #1" in result
    assert "Order #2" in result
    assert "Order #3" in result


@pytest.mark.asyncio
async def test_list_orders_tool_catches_unexpected_exception(mock_service: AsyncMock) -> None:
    """Ensures unexpected exceptions don't bubble up to the LLM."""
    mock_service.list_orders.side_effect = RuntimeError("connection pool exhausted")

    result = await list_orders_tool(service=mock_service, user_id=1)

    assert "Action Failed" in result
    assert "connection pool exhausted" not in result


# ──────────────────────────────────────────────────────────────────────────────
# get_order_details_tool
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_order_details_tool_success(mock_service: AsyncMock) -> None:
    """Ensures fetching a single order formats the details string correctly."""
    now = datetime.now(UTC)
    mock_order = Order(id=55, status=OrderStatus.PROCESSING)
    mock_order.created_at = now
    mock_order.updated_at = now
    mock_service.get_order_details.return_value = mock_order

    result = await get_order_details_tool(service=mock_service, order_id=55)

    assert "Order #55 Details:" in result
    assert "Status: 'processing'" in result
    assert "Created At:" in result
    assert "Last Updated At:" in result
    assert now.isoformat() in result


@pytest.mark.asyncio
async def test_get_order_details_tool_null_timestamps(mock_service: AsyncMock) -> None:
    """Ensures 'Unknown' is shown when timestamps are not populated."""
    mock_order = Order(id=1, status=OrderStatus.PENDING)
    mock_order.created_at = None
    mock_order.updated_at = None
    mock_service.get_order_details.return_value = mock_order

    result = await get_order_details_tool(service=mock_service, order_id=1)

    assert "Created At: Unknown" in result
    assert "Last Updated At: Unknown" in result


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
    mock_service.get_order_details.side_effect = OwnershipError("Order #55 could not be found.")

    result = await get_order_details_tool(service=mock_service, order_id=55, user_id=999)

    assert "Action Failed" in result
    assert "could not be found" in result
