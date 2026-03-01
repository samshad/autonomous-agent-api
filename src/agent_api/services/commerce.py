from __future__ import annotations
from collections.abc import Sequence

import structlog

from agent_api.core.exceptions import BusinessRuleError, EntityNotFoundException, OwnershipError
from agent_api.models.domain import Order, OrderStatus
from agent_api.repository.order_repo import OrderRepository

logger = structlog.get_logger(__name__)

_UNCANCELLABLE_STATUSES: frozenset[OrderStatus] = frozenset({
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED
})


class CommerceService:
    """
    Executes e-commerce business logic.
    Relies on dependency injection for data access.
    """

    def __init__(self, order_repo: OrderRepository) -> None:
        self._order_repo = order_repo

    async def _get_order_or_raise(self, order_id: int) -> Order:
        """
        Fetch an order by id or raise EntityNotFoundException.
        Central lookup used by all public methods to avoid duplication.
        """
        order = await self._order_repo.get_by_id(order_id)
        if not order:
            logger.warning("commerce.order_not_found", order_id=order_id)
            raise EntityNotFoundException(f"Order #{order_id} could not be found.")
        return order

    async def get_order_details(self, order_id: int, user_id: int | None = None) -> Order:
        """
        Retrieve a single order.
        Enforces ownership if user_id is provided, raising OwnershipError if mismatched.
        """
        order = await self._get_order_or_raise(order_id)

        if user_id is not None and order.user_id != user_id:
            logger.warning(
                "commerce.ownership_check_failed",
                order_id=order_id,
                user_id=user_id,
            )
            logger.error("OwnershipError: Ownership check failed", order_id=order_id)
            raise OwnershipError(f"Order #{order_id} could not be found.")

        return order

    async def cancel_order(self, order_id: int, user_id: int | None = None) -> Order:
        """
        Attempt to cancel an order.

        Business rules:
        - Ownership enforced when user_id is provided.
        - Cannot cancel shipped or delivered orders.
        - Idempotent: cancelling an already-cancelled order raises BusinessRuleError
          to make the caller aware the state was not changed.
        """
        order = await self._get_order_or_raise(order_id)

        if user_id is not None and order.user_id != user_id:
            logger.warning(
                "commerce.ownership_check_failed",
                order_id=order_id,
                user_id=user_id,
            )
            raise OwnershipError(
                f"Order #{order_id} could not be found."
            )

        if order.status in _UNCANCELLABLE_STATUSES:
            logger.warning(
                "commerce.cancel_rejected",
                order_id=order_id,
                current_status=order.status,
            )
            raise BusinessRuleError(
                f"Cannot cancel order #{order_id}: already '{order.status.value}'. "
                "Please contact support for returns."
            )

        if order.status == OrderStatus.CANCELLED:
            logger.info("commerce.order_already_cancelled", order_id=order_id)
            raise BusinessRuleError(
                f"Order #{order_id} is already cancelled."
            )

        updated_order = await self._order_repo.update_status(
            order_id=order_id,
            new_status=OrderStatus.CANCELLED,
        )

        if not updated_order:
            logger.error("commerce.order_update_failed", order_id=order_id)
            raise EntityNotFoundException(
                f"Order #{order_id} could not be updated. Please try again."
            )

        logger.info("commerce.order_cancelled", order_id=order_id)
        return updated_order

    async def list_orders(self, user_id: int) -> dict:
        """List all orders for a user, most recent first."""
        orders: Sequence[Order] = await self._order_repo.get_orders_by_user(user_id)
        logger.info("commerce.orders_listed", user_id=user_id, count=len(orders))
        return {
            "orders": [
                {
                    "order_id": o.id,
                    "status": o.status.value,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ],
            "count": len(orders),
        }

