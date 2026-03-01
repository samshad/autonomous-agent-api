# tests/integration/test_order_repo_real_db.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.models.domain import Order, OrderStatus, User
from agent_api.repository.order_repo import OrderRepository


@pytest.mark.asyncio
async def test_update_status_non_existent_order(real_db_session: AsyncSession) -> None:
    """Edge Case: Updating an order ID that does not exist in the database."""
    # Arrange
    repo = OrderRepository(session=real_db_session)
    invalid_order_id = 999999

    # Act
    result = await repo.update_status(
        order_id=invalid_order_id,
        new_status=OrderStatus.CANCELLED
    )

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_get_orders_for_user_with_no_orders(real_db_session: AsyncSession) -> None:
    """Edge Case: Fetching orders for a newly created user with zero history."""
    # Arrange
    new_user = User(email="no_orders@example.com", full_name="Ghost User")
    real_db_session.add(new_user)
    await real_db_session.flush()  # Flush to get the ID without committing the top-level transaction

    repo = OrderRepository(session=real_db_session)

    # Act
    orders = await repo.get_orders_by_user(user_id=new_user.id)

    # Assert
    assert len(orders) == 0
    assert isinstance(orders, list)


@pytest.mark.asyncio
async def test_successful_status_update_is_isolated(real_db_session: AsyncSession) -> None:
    """
    Standard Case: Verify repository works, but relies on the fixture
    to ensure this data doesn't permanently exist after the test.
    """
    # Arrange
    user = User(email="isolation_test@example.com", full_name="Isolated User")
    real_db_session.add(user)
    await real_db_session.flush()

    order = Order(user_id=user.id, status=OrderStatus.PENDING)
    real_db_session.add(order)
    await real_db_session.flush()

    repo = OrderRepository(session=real_db_session)

    # Act
    updated_order = await repo.update_status(
        order_id=order.id,
        new_status=OrderStatus.SHIPPED
    )
    # Simulate a service layer commit
    await real_db_session.commit()

    # Assert
    assert updated_order is not None
    assert updated_order.status == OrderStatus.SHIPPED
