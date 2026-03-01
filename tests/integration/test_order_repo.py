import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.models.domain import Order, OrderStatus, User
from agent_api.repository.order_repo import OrderRepository


@pytest.mark.asyncio
async def test_order_repository_updates_status(real_db_session: AsyncSession) -> None:
    """Ensures the repository can fetch and update an order's status
    against the real Postgres database.  Rolled back at teardown."""

    # Arrange: Seed the database
    user = User(email="repo_test@example.com", full_name="Test User")
    order = Order(user=user, status=OrderStatus.PENDING)
    real_db_session.add_all([user, order])
    await real_db_session.commit()

    # Initialize the repository with the active session
    repo = OrderRepository(session=real_db_session)

    # Act: Update the status via the repository
    updated_order = await repo.update_status(
        order_id=order.id,
        new_status=OrderStatus.SHIPPED,
    )

    # Simulate the service layer commit
    await real_db_session.commit()

    # Assert: Verify the state
    assert updated_order is not None
    assert updated_order.status == OrderStatus.SHIPPED

    # Verify the database actually persisted the change
    fetched_order = await repo.get_by_id(order.id)
    assert fetched_order is not None
    assert fetched_order.status == OrderStatus.SHIPPED
