from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from pydantic import BaseModel, Field

from agent_api.agent.registry import registry
from agent_api.core.exceptions import AgentAPIError
from agent_api.services.commerce import CommerceService

logger = structlog.get_logger(__name__)


# ── DRY helper: wraps every tool so domain errors become LLM-readable strings ──
def safe_tool_execution(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """
    Decorator that catches domain and unexpected exceptions in tool functions,
    converting them into safe natural-language strings for the ReAct loop.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return await func(*args, **kwargs)
        except AgentAPIError as e:
            logger.warning("tool.domain_error", tool=func.__name__, error=e.message)
            return f"Action Failed: {e.message}"
        except Exception as e:
            logger.error("tool.unexpected_error", tool=func.__name__, error=str(e))
            return (
                "Action Failed: An unexpected system error occurred "
                f"while executing {func.__name__}."
            )

    return wrapper


# ── Pydantic Argument Schemas ────────────────────────────────────────────────


class CancelOrderArgs(BaseModel):
    """Arguments required to cancel an order."""

    order_id: int = Field(
        ...,
        description="The unique numerical ID of the order to cancel. Do NOT guess this. "
        "Ask the user if missing.",
    )
    user_id: int | None = Field(
        default=None, description="The numerical ID of the user requesting the cancellation."
    )


class ListOrdersArgs(BaseModel):
    """Arguments required to list a user's orders."""

    user_id: int = Field(
        ..., description="The unique numerical ID of the user whose orders are being requested."
    )


class GetOrderDetailsArgs(BaseModel):
    """Arguments required to fetch the details of a specific order."""

    order_id: int = Field(..., description="The unique numerical ID of the order to look up.")
    user_id: int | None = Field(
        default=None, description="The numerical ID of the user requesting the details."
    )


# ── Tool Implementations ────────────────────────────────────────────────────


@registry.register(args_schema=CancelOrderArgs)
@safe_tool_execution
async def cancel_order_tool(
    service: CommerceService, order_id: int, user_id: int | None = None
) -> str:
    """
    Use this tool to cancel an existing e-commerce order.

    Returns:
        A natural language string describing the success or failure of the action.
    """
    order = await service.cancel_order(order_id=order_id, user_id=user_id)
    created = order.created_at.isoformat() if order.created_at else "Unknown"
    updated = order.updated_at.isoformat() if order.updated_at else "Unknown"
    return (
        f"Success: Order #{order.id} has been successfully cancelled. "
        f"New status is '{order.status.value}'. "
        f"Originally created at: {created}. Last updated at: {updated}."
    )


@registry.register(args_schema=ListOrdersArgs)
@safe_tool_execution
async def list_orders_tool(service: CommerceService, user_id: int) -> str:
    """
    Use this tool to retrieve a list of all orders belonging to a specific user.
    Provides the order IDs, current status, and creation dates.

    Returns:
        A formatted string of the user's order history or a failure message.
    """
    result = await service.list_orders(user_id=user_id)
    if result["count"] == 0:
        return f"User #{user_id} currently has no order history."

    orders_str = "\n".join(
        [
            f"- Order #{o['order_id']} | Status: {o['status']} "
            f"| Created: {o['created_at']} | Last Updated: {o['updated_at']}"
            for o in result["orders"]
        ]
    )
    logger.info("tool.list_orders_success", user_id=user_id, count=result["count"])
    return f"Found {result['count']} orders for User #{user_id}:\n{orders_str}"


@registry.register(args_schema=GetOrderDetailsArgs)
@safe_tool_execution
async def get_order_details_tool(
    service: CommerceService, order_id: int, user_id: int | None = None
) -> str:
    """
    Use this tool to retrieve the details (status, creation date) of a single specific order.
    """
    order = await service.get_order_details(order_id=order_id, user_id=user_id)

    created_str = order.created_at.isoformat() if order.created_at else "Unknown"
    updated_str = order.updated_at.isoformat() if order.updated_at else "Unknown"
    return (
        f"Order #{order.id} Details:\n"
        f"- Status: '{order.status.value}'\n"
        f"- Created At: {created_str}\n"
        f"- Last Updated At: {updated_str}"
    )


def init_tools() -> None:
    """
    Dummy function called during app startup.
    Ensures this module is imported and the @registry decorators are evaluated.
    """
    pass
