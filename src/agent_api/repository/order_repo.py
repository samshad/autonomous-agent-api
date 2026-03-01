from __future__ import annotations

from collections.abc import Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.models.domain import Order, OrderStatus

logger = structlog.get_logger(__name__)


class OrderRepository:
    """
    Abstracts database operations for the Order entity.
    Requires an active AsyncSession injected at instantiation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id: int) -> Order | None:
        """Fetches a single order by its primary key."""
        stmt = select(Order).where(Order.id == order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_orders_by_user(self, user_id: int) -> Sequence[Order]:
        """Retrieves all orders associated with a specific user."""
        stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(self, order_id: int, new_status: OrderStatus) -> Order | None:
        """
        Updates the status of an existing order.
        Note: This does NOT commit the transaction to maintain service-layer control.
        """
        order = await self.get_by_id(order_id)
        if not order:
            logger.warning("order_not_found_for_update", order_id=order_id)
            return None

        order.status = new_status
        await self._session.flush()

        logger.info("order_status_updated", order_id=order_id, new_status=new_status.value)
        return order
