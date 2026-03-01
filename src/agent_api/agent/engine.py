from __future__ import annotations

import inspect

import structlog

from agent_api.agent.llm_client import LLMClient
from agent_api.agent.registry import registry
from agent_api.core.config import settings
from agent_api.models.agent import Message
from agent_api.services.commerce import CommerceService

logger = structlog.get_logger(__name__)

MAX_REACT_ITERATIONS = settings.max_react_iterations


class AgentEngine:
    """
    Orchestrates the ReAct (Reason + Act) loop.
    Decoupled from specific LLMs (via LLMClient) and HTTP APIs.
    """

    def __init__(self, llm_client: LLMClient, commerce_service: CommerceService) -> None:
        self.llm = llm_client
        self.service = commerce_service
        self.tools_schema = registry.get_all_schemas()
        self.max_loops = MAX_REACT_ITERATIONS

    async def _execute_tool(self, tool_name: str, arguments: dict, user_id: int | None) -> str:
        """Dynamically validates and safely executes a tool from the registry."""
        tool = registry.get_tool(tool_name)
        if not tool:
            logger.warning("engine.tool_not_found", tool_name=tool_name)
            return f"Action Failed: Tool '{tool_name}' does not exist."

        try:
            validated_args_model = tool.args_schema(**arguments)

            clean_arguments = validated_args_model.model_dump()

            sig = inspect.signature(tool.func)
            if "user_id" in sig.parameters:
                clean_arguments["user_id"] = user_id

            return await tool.func(service=self.service, **clean_arguments)

        except Exception as e:
            logger.error("engine.tool_execution_failed", tool_name=tool_name, error=str(e))
            return f"Action Failed: {str(e)}"

    async def run(self, user_prompt: str, user_id: int | None = None) -> str:
        """
        Executes the autonomous conversation loop until the AI resolves the
        intent or safely aborts.
        """
        auth_context = (f"The current authenticated user has user_id={user_id}. "
                        f"Always use this user_id when calling tools.") if user_id else "The user is unauthenticated."
        system_prompt = (
            "You are a helpful, professional customer support agent for an e-commerce platform. "
            f"{auth_context} "
            "Use the provided tools to look up orders, cancel orders, "
            "or list orders when the user asks. "
            "Always use the exact parameters the tools require (e.g. order number or user ID). "
            "If a user asks to cancel an order but doesn't provide an order ID, ask them for it. "
            "Do NOT guess order IDs or make up information. "
            "Base your answers strictly on tool outputs."
            "Reply in natural language after each tool result. "
            "When the user's request is fully handled, give a clear final reply."
        )

        messages: list[Message] = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        loop_count = 0
        while loop_count < self.max_loops:
            loop_count += 1
            logger.info("engine.react_loop_start", iteration=loop_count)

            # 1. Reason (Ask LLM what to do next)
            response_msg = await self.llm.chat(messages=messages, tools=self.tools_schema)
            messages.append(response_msg)

            # 2. Act (Check if the LLM decided to use a tool, or respond directly)
            if not response_msg.tool_calls:
                logger.info("engine.react_loop_complete", iteration=loop_count)
                return response_msg.content or "I couldn't generate a response."

            # 3. Observe (Execute the requested tools and feed the results back)
            for tool_call in response_msg.tool_calls:
                logger.info(
                    "engine.executing_tool",
                    tool_name=tool_call.function.name,
                    args=tool_call.function.arguments,
                )

                result_str = await self._execute_tool(
                    tool_name=tool_call.function.name,
                    arguments=tool_call.function.arguments,
                    user_id=user_id,
                )

                messages.append(Message(role="tool", content=result_str, tool_call_id=tool_call.id))

        logger.warning("engine.max_loops_exceeded")
        return (
            "I'm sorry, I've encountered a complex issue and need to stop."
            " Please try your request again."
        )
