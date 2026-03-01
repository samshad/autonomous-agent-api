from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from agent_api.core.exceptions import AgentAPIException
from agent_api.services.commerce import CommerceService

logger = structlog.get_logger(__name__)


class CancelOrderArgs(BaseModel):
    """Arguments required to cancel an order."""
    order_id: int = Field(
        ...,
        description="The unique numerical ID of the order to cancel. Do NOT guess this. Ask the user if missing."
    )
    user_id: int | None = Field(
        default=None,
        description="The numerical ID of the user requesting the cancellation."
    )


class ListOrdersArgs(BaseModel):
    """Arguments required to list a user's orders."""
    user_id: int = Field(
        ...,
        description="The unique numerical ID of the user whose orders are being requested."
    )


class GetOrderDetailsArgs(BaseModel):
    """Arguments required to fetch the details of a specific order."""
    order_id: int = Field(
        ...,
        description="The unique numerical ID of the order to look up."
    )
    user_id: int | None = Field(
        default=None,
        description="The numerical ID of the user requesting the details."
    )


async def cancel_order_tool(
        service: CommerceService,
        order_id: int,
        user_id: int | None = None
) -> str:
    """
    Use this tool to cancel an existing e-commerce order.

    Returns:
        A natural language string describing the success or failure of the action.
    """
    try:
        order = await service.cancel_order(order_id=order_id, user_id=user_id)
        return f"Success: Order #{order.id} has been successfully cancelled. New status is '{order.status.value}'."
    except AgentAPIException as e:
        # Crucial: We do not raise HTTP exceptions to the LLM.
        # We catch domain errors and return them as strings so the ReAct loop
        # can read the error and inform the user conversationally.
        logger.error("tool.cancel_order_unexpected_error: AgentAPIException", error=str(e))
        return f"Action Failed: {e.message}"
    except Exception as e:
        logger.error("tool.cancel_order_unexpected_error", error=str(e))
        return "Action Failed: An unexpected system error occurred while attempting to cancel the order."


async def list_orders_tool(
        service: CommerceService,
        user_id: int
) -> str:
    """
    Use this tool to retrieve a list of all orders belonging to a specific user.
    Provides the order IDs, current status, and creation dates.

    Returns:
        A formatted string of the user's order history or a failure message.
    """
    try:
        result = await service.list_orders(user_id=user_id)
        if result["count"] == 0:
            return f"User #{user_id} currently has no order history."

        orders_str = "\n".join(
            [f"- Order #{o['order_id']} | Status: {o['status']} | Date: {o['created_at']}"
             for o in result["orders"]]
        )
        logger.info(f"tool.list_orders_success: User #{user_id} has {result['count']} orders.")
        return f"Found {result['count']} orders for User #{user_id}:\n{orders_str}"
    except AgentAPIException as e:
        logger.error("tool.list_orders_unexpected_error: AgentAPIException", error=str(e))
        return f"Action Failed: {e.message}"
    except Exception as e:
        logger.error("tool.list_orders_unexpected_error", error=str(e))
        return "Action Failed: An unexpected system error occurred while listing orders."


async def get_order_details_tool(
        service: CommerceService,
        order_id: int,
        user_id: int | None = None
) -> str:
    """
    Use this tool to retrieve the details (status, creation date) of a single specific order.
    """
    try:
        order = await service.get_order_details(order_id=order_id, user_id=user_id)

        date_str = order.created_at.isoformat() if order.created_at else "Unknown date"
        return (
            f"Order #{order.id} Details:\n"
            f"- Status: '{order.status.value}'\n"
            f"- Created At: {date_str}"
        )
    except AgentAPIException as e:
        logger.error("tool.get_order_details_unexpected_error: AgentAPIException", error=str(e))
        return f"Action Failed: {e.message}"
    except Exception as e:
        logger.error("tool.get_order_details_unexpected_error", error=str(e))
        return "Action Failed: An unexpected system error occurred while fetching order details."
