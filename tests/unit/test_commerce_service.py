from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from agent_api.core.exceptions import (
    BusinessRuleError,
    EntityNotFoundError,
    OwnershipError,
)
from agent_api.models.domain import Order, OrderStatus
from agent_api.services.commerce import CommerceService


@pytest.fixture
def mock_order_repo() -> AsyncMock:
    """Provides a mocked OrderRepository."""
    return AsyncMock()


@pytest.fixture
def commerce_service(mock_order_repo: AsyncMock) -> CommerceService:
    """Injects the mocked repo into the CommerceService."""
    return CommerceService(order_repo=mock_order_repo)


# ──────────────────────────────────────────────────────────────────────────────
# get_order_details
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_order_details_success(commerce_service: CommerceService, mock_order_repo: AsyncMock) -> None:
    """Ensures a valid order is returned successfully."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order

    result = await commerce_service.get_order_details(order_id=1)

    assert result == mock_order
    mock_order_repo.get_by_id.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_order_details_not_found(commerce_service: CommerceService, mock_order_repo: AsyncMock) -> None:
    """Ensures EntityNotFoundError is raised when order doesn't exist."""
    mock_order_repo.get_by_id.return_value = None

    with pytest.raises(EntityNotFoundError) as exc_info:
        await commerce_service.get_order_details(order_id=999)

    assert "could not be found" in str(exc_info.value)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_order_details_with_matching_ownership(
    commerce_service: CommerceService, mock_order_repo: AsyncMock
) -> None:
    """Ensures get_order_details succeeds when user_id matches the order's owner."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order

    result = await commerce_service.get_order_details(order_id=1, user_id=100)

    assert result == mock_order


@pytest.mark.asyncio
async def test_get_order_details_ownership_mismatch(
    commerce_service: CommerceService, mock_order_repo: AsyncMock
) -> None:
    """Ensures OwnershipError (404) is raised when user_id doesn't match order owner."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order

    with pytest.raises(OwnershipError) as exc_info:
        await commerce_service.get_order_details(order_id=1, user_id=999)

    # Security: returns 404, not 403, to avoid leaking existence
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_order_details_no_user_id_skips_ownership(
    commerce_service: CommerceService, mock_order_repo: AsyncMock
) -> None:
    """Ensures ownership check is skipped when user_id is None (system/admin call)."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order

    result = await commerce_service.get_order_details(order_id=1, user_id=None)

    assert result == mock_order


# ──────────────────────────────────────────────────────────────────────────────
# cancel_order
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_order_success_with_ownership(commerce_service: CommerceService,
                                                   mock_order_repo: AsyncMock) -> None:
    """Ensures a pending order is cancelled when ownership matches."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order
    mock_order_repo.update_status.return_value = Order(id=1, user_id=100, status=OrderStatus.CANCELLED)

    result = await commerce_service.cancel_order(order_id=1, user_id=100)

    assert result.status == OrderStatus.CANCELLED
    mock_order_repo.update_status.assert_called_once_with(order_id=1, new_status=OrderStatus.CANCELLED)


@pytest.mark.asyncio
async def test_cancel_order_success_without_user_id(
    commerce_service: CommerceService, mock_order_repo: AsyncMock
) -> None:
    """Ensures a cancel succeeds when no user_id is provided (system-level call)."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order
    mock_order_repo.update_status.return_value = Order(id=1, user_id=100, status=OrderStatus.CANCELLED)

    result = await commerce_service.cancel_order(order_id=1, user_id=None)

    assert result.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_processing_order_succeeds(
    commerce_service: CommerceService, mock_order_repo: AsyncMock
) -> None:
    """Ensures a processing order can still be cancelled (only shipped/delivered blocked)."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PROCESSING)
    mock_order_repo.get_by_id.return_value = mock_order
    mock_order_repo.update_status.return_value = Order(id=1, user_id=100, status=OrderStatus.CANCELLED)

    result = await commerce_service.cancel_order(order_id=1)

    assert result.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_order_ownership_error(commerce_service: CommerceService, mock_order_repo: AsyncMock) -> None:
    """Ensures OwnershipError is raised if user_id doesn't match the order's owner."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order

    with pytest.raises(OwnershipError) as exc_info:
        await commerce_service.cancel_order(order_id=1, user_id=999)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_cancel_order_not_found(
    commerce_service: CommerceService, mock_order_repo: AsyncMock
) -> None:
    """Ensures EntityNotFoundError is raised when order doesn't exist."""
    mock_order_repo.get_by_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        await commerce_service.cancel_order(order_id=999)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_status", [OrderStatus.SHIPPED, OrderStatus.DELIVERED])
async def test_cancel_order_shipped_or_delivered(
        commerce_service: CommerceService, mock_order_repo: AsyncMock, invalid_status: OrderStatus
) -> None:
    """Ensures BusinessRuleError prevents cancelling shipped or delivered orders."""
    mock_order = Order(id=1, user_id=100, status=invalid_status)
    mock_order_repo.get_by_id.return_value = mock_order

    with pytest.raises(BusinessRuleError) as exc_info:
        await commerce_service.cancel_order(order_id=1)

    assert "Cannot cancel order" in str(exc_info.value)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_cancel_order_already_cancelled(commerce_service: CommerceService, mock_order_repo: AsyncMock) -> None:
    """Ensures an idempotent BusinessRuleError is raised if already cancelled."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.CANCELLED)
    mock_order_repo.get_by_id.return_value = mock_order

    with pytest.raises(BusinessRuleError) as exc_info:
        await commerce_service.cancel_order(order_id=1)

    assert "already cancelled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancel_order_update_fails(commerce_service: CommerceService, mock_order_repo: AsyncMock) -> None:
    """Ensures EntityNotFoundError is raised if the update mysteriously fails mid-transaction."""
    mock_order = Order(id=1, user_id=100, status=OrderStatus.PENDING)
    mock_order_repo.get_by_id.return_value = mock_order
    mock_order_repo.update_status.return_value = None

    with pytest.raises(EntityNotFoundError):
        await commerce_service.cancel_order(order_id=1)


# ──────────────────────────────────────────────────────────────────────────────
# list_orders
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_orders_success(commerce_service: CommerceService, mock_order_repo: AsyncMock) -> None:
    """Ensures list_orders formats the database entities into the correct dictionary schema."""
    now = datetime.now(UTC)
    mock_orders = [
        Order(id=10, user_id=5, status=OrderStatus.DELIVERED, created_at=now, updated_at=now),
        Order(id=11, user_id=5, status=OrderStatus.PENDING, created_at=now, updated_at=now),
    ]
    mock_order_repo.get_orders_by_user.return_value = mock_orders

    result = await commerce_service.list_orders(user_id=5)

    assert result["count"] == 2
    assert len(result["orders"]) == 2
    assert result["orders"][0]["order_id"] == 10
    assert result["orders"][0]["status"] == "delivered"
    assert result["orders"][0]["created_at"] == now.isoformat()
    assert result["orders"][0]["updated_at"] == now.isoformat()
    mock_order_repo.get_orders_by_user.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_list_orders_empty(commerce_service: CommerceService, mock_order_repo: AsyncMock) -> None:
    """Ensures an empty list is returned when the user has no orders."""
    mock_order_repo.get_orders_by_user.return_value = []

    result = await commerce_service.list_orders(user_id=42)

    assert result["count"] == 0
    assert result["orders"] == []


@pytest.mark.asyncio
async def test_list_orders_handles_null_timestamps(
    commerce_service: CommerceService, mock_order_repo: AsyncMock
) -> None:
    """Ensures None timestamps don't crash the serializer."""
    mock_order = Order(id=1, user_id=5, status=OrderStatus.PENDING)
    # created_at and updated_at are None (not loaded / not set)
    mock_order.created_at = None
    mock_order.updated_at = None
    mock_order_repo.get_orders_by_user.return_value = [mock_order]

    result = await commerce_service.list_orders(user_id=5)

    assert result["orders"][0]["created_at"] is None
    assert result["orders"][0]["updated_at"] is None

