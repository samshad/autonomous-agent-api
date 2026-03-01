import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.models.domain import Order, OrderStatus, User


@pytest.mark.asyncio
async def test_create_and_query_user_with_order(real_db_session: AsyncSession) -> None:
    """Verifies that ORM models persist and relationships function correctly
    against the real Postgres database.  Rolled back at teardown."""

    # Arrange: Create a user and an order
    new_user = User(email="domain_test@example.com", full_name="Alice Smith")
    new_order = Order(user=new_user, status=OrderStatus.PENDING)

    real_db_session.add(new_user)
    real_db_session.add(new_order)
    await real_db_session.commit()  # becomes a savepoint — rolled back later

    # Act: Query the user back
    stmt = select(User).where(User.email == "domain_test@example.com")
    result = await real_db_session.execute(stmt)
    saved_user = result.scalar_one_or_none()

    # Assert
    assert saved_user is not None
    assert saved_user.full_name == "Alice Smith"

    order_stmt = select(Order).where(Order.user_id == saved_user.id)
    order_result = await real_db_session.execute(order_stmt)
    saved_order = order_result.scalar_one_or_none()

    assert saved_order is not None
    assert saved_order.status == OrderStatus.PENDING
