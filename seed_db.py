import asyncio
from decimal import Decimal

import structlog
from alembic import command
from alembic.config import Config

from agent_api.core.config import settings
from agent_api.core.database import DatabaseManager
from agent_api.models.domain import Order, OrderItem, OrderStatus, Product, User
from agent_api.repository.order_repo import OrderRepository

logger = structlog.get_logger(__name__)


def run_migrations() -> None:
    """Run Alembic migrations to HEAD so the schema is always up-to-date."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.info("alembic_migrations_applied")


async def main() -> None:
    """
    Applies Alembic migrations, seeds dummy data, and tests repository functions.
    """
    logger.info("connecting_to_database", url=settings.database_url)

    # 1. Apply schema migrations via Alembic
    run_migrations()

    db_manager = DatabaseManager(database_url=settings.database_url, echo=False)


    async with db_manager.session() as session:
        logger.info("seeding_dummy_data")

        u1 = User(email="test.user@example.com", full_name="Test User")
        u2 = User(email="alice@example.com", full_name="Alice")
        u3 = User(email="bob@example.com", full_name="Bob")
        session.add_all([u1, u2, u3])

        p1 = Product(name="Mechanical Keyboard", price=Decimal("149.99"), inventory_count=50)
        p2 = Product(name="Widget A", price=Decimal("29.99"), inventory_count=5)
        p3 = Product(name="Widget B", price=Decimal("49.99"), inventory_count=60)
        session.add_all([p1, p2, p3])

        await session.flush()

        o1 = Order(user_id=u1.id, status=OrderStatus.PENDING)
        o2 = Order(user_id=u2.id, status=OrderStatus.PROCESSING)
        o3 = Order(user_id=u3.id, status=OrderStatus.SHIPPED)
        session.add_all([o1, o2, o3])
        await session.flush()

        ot1 = OrderItem(order_id=o1.id, product_id=p1.id, quantity=1, unit_price=p1.price)
        ot2 = OrderItem(order_id=o2.id, product_id=p2.id, quantity=2, unit_price=p3.price)
        ot3 = OrderItem(order_id=o3.id, product_id=p3.id, quantity=3, unit_price=p3.price)

        session.add_all([ot1, ot2, ot3])

        await session.commit()

        logger.info("seed_data_inserted", user_id=u1, order_id=o1.id)
        logger.info("seed_data_inserted", user_id=u2, order_id=o2.id)
        logger.info("seed_data_inserted", user_id=u3, order_id=o3.id)

        test_user_id = u1.id

    async with db_manager.session() as session:
        logger.info("testing_repository_layer")
        repo = OrderRepository(session=session)

        orders = await repo.get_orders_by_user(user_id=test_user_id)
        logger.info("fetched_orders", count=len(orders), status=orders[0].status.value)

        target_order_id = orders[0].id
        updated_order = await repo.update_status(
            order_id=target_order_id, new_status=OrderStatus.PROCESSING
        )

        await session.commit()

        if updated_order:
            logger.info("order_status_updated", final_status=updated_order.status.value)
        else:
            logger.error("order_update_failed")

    await db_manager.dispose()


if __name__ == "__main__":
    asyncio.run(main())
