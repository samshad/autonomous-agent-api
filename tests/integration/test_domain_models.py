import pytest
from sqlalchemy import select

from agent_api.core.database import DatabaseManager
from agent_api.models.domain import Base, Order, OrderStatus, User


@pytest.fixture
async def db_manager():
    """Provides a fresh database manager for testing."""
    manager = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")
    # Create all tables for the test
    async with manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield manager

    # Teardown
    await manager.dispose()


@pytest.mark.asyncio
async def test_create_and_query_user_with_order(db_manager: DatabaseManager) -> None:
    """Verifies that ORM models persist and relationships function correctly."""
    async with db_manager.session() as session:
        # Arrange: Create a user and an order
        new_user = User(email="customer@example.com", full_name="Alice Smith")
        new_order = Order(user=new_user, status=OrderStatus.PENDING)

        session.add(new_user)
        session.add(new_order)
        await session.commit()

        # Act: Query the user back with their orders
        stmt = select(User).where(User.email == "customer@example.com")
        result = await session.execute(stmt)
        saved_user = result.scalar_one_or_none()

        # Assert
        assert saved_user is not None
        assert saved_user.full_name == "Alice Smith"

        # Lazy loading isn't allowed by default in async SQLAlchemy after commit,
        # but since we haven't expired the session or accessed the relationship yet,
        # we can verify the DB state directly.
        order_stmt = select(Order).where(Order.user_id == saved_user.id)
        order_result = await session.execute(order_stmt)
        saved_order = order_result.scalar_one_or_none()

        assert saved_order is not None
        assert saved_order.status == OrderStatus.PENDING
