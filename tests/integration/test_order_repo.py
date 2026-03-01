import pytest

from agent_api.core.database import DatabaseManager
from agent_api.models.domain import Base, Order, OrderStatus, User
from agent_api.repository.order_repo import OrderRepository


@pytest.fixture
async def db_manager():
    """Provides a fresh, isolated in-memory database manager."""
    manager = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")
    async with manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    await manager.dispose()


@pytest.mark.asyncio
async def test_order_repository_updates_status(db_manager: DatabaseManager) -> None:
    """Ensures the repository can fetch and update an order's status."""
    async with db_manager.session() as session:
        # Arrange: Seed the database
        user = User(email="repo_test@example.com", full_name="Test User")
        order = Order(user=user, status=OrderStatus.PENDING)
        session.add_all([user, order])
        await session.commit()

        # Initialize the repository with the active session
        repo = OrderRepository(session=session)

        # Act: Update the status via the repository
        updated_order = await repo.update_status(
            order_id=order.id,
            new_status=OrderStatus.SHIPPED
        )

        # We explicitly commit here simulating the Service layer
        await session.commit()

        # Assert: Verify the state
        assert updated_order is not None
        assert updated_order.status == OrderStatus.SHIPPED

        # Verify the database actually persisted the change
        fetched_order = await repo.get_by_id(order.id)
        assert fetched_order is not None
        assert fetched_order.status == OrderStatus.SHIPPED
