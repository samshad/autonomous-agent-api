from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from agent_api.agent.engine import AgentEngine
from agent_api.agent.registry import Tool
from agent_api.models.agent import Message, ToolCall, ToolCallFunction
from agent_api.services.commerce import CommerceService


# --- Dummy Setup for Testing ---

class DummyArgs(BaseModel):
    order_id: int
    user_id: int | None = None


async def dummy_action(service: CommerceService, order_id: int, user_id: int | None = None) -> str:
    return f"Processed {order_id} for user {user_id}"


dummy_tool = Tool(
    name="dummy_action",
    description="A dummy action.",
    func=dummy_action,
    args_schema=DummyArgs
)


@pytest.fixture
def mock_service() -> AsyncMock:
    return AsyncMock(spec=CommerceService)


@pytest.fixture
def mock_llm() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def engine(mock_llm: AsyncMock, mock_service: AsyncMock) -> AgentEngine:
    with patch("agent_api.agent.engine.registry.get_all_schemas", return_value=[]):
        return AgentEngine(llm_client=mock_llm, commerce_service=mock_service)


# ──────────────────────────────────────────────────────────────────────────────
# _execute_tool
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("agent_api.agent.engine.registry.get_tool", return_value=dummy_tool)
async def test_execute_tool_success_with_idor_injection(mock_get_tool: AsyncMock, engine: AgentEngine) -> None:
    """Ensures Pydantic validation and trusted user_id injection work correctly."""
    args = {"order_id": 123, "user_id": 999}

    result = await engine._execute_tool("dummy_action", args, user_id=42)

    assert result == "Processed 123 for user 42"
    mock_get_tool.assert_called_once_with("dummy_action")


@pytest.mark.asyncio
@patch("agent_api.agent.engine.registry.get_tool", return_value=dummy_tool)
async def test_execute_tool_pydantic_validation_error(mock_get_tool: AsyncMock, engine: AgentEngine) -> None:
    """Ensures LLM hallucinations (bad data types) are caught and stringified."""
    args = {"order_id": "one hundred twenty three"}

    result = await engine._execute_tool("dummy_action", args, user_id=42)

    assert "Action Failed" in result
    assert "validation error" in result.lower()


@pytest.mark.asyncio
@patch("agent_api.agent.engine.registry.get_tool", return_value=None)
async def test_execute_tool_not_found_in_registry(mock_get_tool: AsyncMock, engine: AgentEngine) -> None:
    """Ensures a clear failure message when the LLM hallucinates a non-existent tool."""
    result = await engine._execute_tool("nonexistent_tool", {}, user_id=1)

    assert "Action Failed" in result
    assert "does not exist" in result


@pytest.mark.asyncio
@patch("agent_api.agent.engine.registry.get_tool", return_value=dummy_tool)
async def test_execute_tool_without_user_id(mock_get_tool: AsyncMock, engine: AgentEngine) -> None:
    """Ensures tool execution works when user_id is None (unauthenticated)."""
    args = {"order_id": 10}

    result = await engine._execute_tool("dummy_action", args, user_id=None)

    assert result == "Processed 10 for user None"


@pytest.mark.asyncio
@patch("agent_api.agent.engine.registry.get_tool", return_value=dummy_tool)
async def test_execute_tool_missing_required_arg(mock_get_tool: AsyncMock, engine: AgentEngine) -> None:
    """Ensures Pydantic catches missing required arguments from the LLM."""
    args = {}  # Missing required 'order_id'

    result = await engine._execute_tool("dummy_action", args, user_id=1)

    assert "Action Failed" in result


# ──────────────────────────────────────────────────────────────────────────────
# run (ReAct loop)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_direct_response(engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine returns immediately if the LLM doesn't call a tool."""
    mock_llm.chat.return_value = Message(
        role="assistant",
        content="Hello! How can I help you today?",
        tool_calls=None
    )

    result = await engine.run(user_prompt="Hi", user_id=42)

    assert result == "Hello! How can I help you today?"
    assert mock_llm.chat.call_count == 1


@pytest.mark.asyncio
async def test_run_null_content_returns_fallback(engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine returns a fallback message when LLM returns None content."""
    mock_llm.chat.return_value = Message(
        role="assistant",
        content=None,
        tool_calls=None,
    )

    result = await engine.run(user_prompt="Hi", user_id=42)

    assert result == "I couldn't generate a response."


@pytest.mark.asyncio
async def test_run_without_user_id(engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine operates correctly without authentication (user_id=None)."""
    mock_llm.chat.return_value = Message(
        role="assistant",
        content="I see you are not logged in.",
        tool_calls=None,
    )

    result = await engine.run(user_prompt="Who am I?", user_id=None)

    assert result == "I see you are not logged in."
    # Verify the system prompt mentions unauthenticated
    call_args = mock_llm.chat.call_args
    system_msg = call_args.kwargs["messages"][0] if call_args.kwargs else call_args[1]["messages"][0]
    assert "unauthenticated" in system_msg.content.lower()


@pytest.mark.asyncio
@patch("agent_api.agent.engine.AgentEngine._execute_tool", return_value="Tool execution was successful.")
async def test_run_with_tool_call(mock_execute: AsyncMock, engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine executes tools and feeds the observation back to the LLM."""
    msg1 = Message(
        role="assistant",
        tool_calls=[
            ToolCall(
                id="call_123",
                type="function",
                function=ToolCallFunction(name="dummy_action", arguments={"order_id": 1})
            )
        ]
    )
    msg2 = Message(
        role="assistant",
        content="I have successfully processed your order."
    )
    mock_llm.chat.side_effect = [msg1, msg2]

    result = await engine.run(user_prompt="Process order 1", user_id=42)

    assert result == "I have successfully processed your order."
    assert mock_llm.chat.call_count == 2
    mock_execute.assert_called_once_with(
        tool_name="dummy_action",
        arguments={"order_id": 1},
        user_id=42
    )


@pytest.mark.asyncio
@patch("agent_api.agent.engine.AgentEngine._execute_tool", return_value="Done.")
async def test_run_with_multiple_tool_calls_in_single_response(
    mock_execute: AsyncMock, engine: AgentEngine, mock_llm: AsyncMock
) -> None:
    """Ensures the engine processes all tool calls when the LLM invokes multiple tools at once."""
    msg1 = Message(
        role="assistant",
        tool_calls=[
            ToolCall(
                id="call_a",
                type="function",
                function=ToolCallFunction(name="tool_a", arguments={"order_id": 1}),
            ),
            ToolCall(
                id="call_b",
                type="function",
                function=ToolCallFunction(name="tool_b", arguments={"order_id": 2}),
            ),
        ],
    )
    msg2 = Message(role="assistant", content="Both tools completed.")
    mock_llm.chat.side_effect = [msg1, msg2]

    result = await engine.run(user_prompt="Do two things", user_id=1)

    assert result == "Both tools completed."
    assert mock_execute.call_count == 2


@pytest.mark.asyncio
async def test_run_max_loops_exceeded(engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine aborts if the LLM gets stuck in an infinite tool-calling loop."""
    engine.max_loops = 2

    stubborn_msg = Message(
        role="assistant",
        tool_calls=[
            ToolCall(
                id="call_loop",
                type="function",
                function=ToolCallFunction(name="dummy_action", arguments={})
            )
        ]
    )
    mock_llm.chat.return_value = stubborn_msg

    with patch("agent_api.agent.engine.AgentEngine._execute_tool", return_value="Result"):
        result = await engine.run(user_prompt="Do something", user_id=42)

    assert "complex issue and need to stop" in result
    assert mock_llm.chat.call_count == 2


@pytest.mark.asyncio
async def test_run_llm_raises_runtime_error(engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures a RuntimeError from the LLM client propagates and is not silently swallowed."""
    mock_llm.chat.side_effect = RuntimeError("Failed to communicate with LLM")

    with pytest.raises(RuntimeError, match="Failed to communicate"):
        await engine.run(user_prompt="Hello", user_id=1)

