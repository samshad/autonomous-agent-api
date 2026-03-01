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
    # Patch get_all_schemas to return empty list during engine initialization to avoid dependencies
    with patch("agent_api.agent.engine.registry.get_all_schemas", return_value=[]):
        return AgentEngine(llm_client=mock_llm, commerce_service=mock_service)


# --- Test Cases ---

@pytest.mark.asyncio
@patch("agent_api.agent.engine.registry.get_tool", return_value=dummy_tool)
async def test_execute_tool_success_with_idor_injection(mock_get_tool: AsyncMock, engine: AgentEngine) -> None:
    """Ensures Pydantic validation and trusted user_id injection work correctly."""
    # Arrange: LLM attempts to pass a malicious user_id
    args = {"order_id": 123, "user_id": 999}

    # Act: Engine is called with the trusted HTTP user_id (e.g., 42)
    result = await engine._execute_tool("dummy_action", args, user_id=42)

    # Assert: The engine must forcefully overwrite the LLM's user_id with 42
    assert result == "Processed 123 for user 42"
    mock_get_tool.assert_called_once_with("dummy_action")


@pytest.mark.asyncio
@patch("agent_api.agent.engine.registry.get_tool", return_value=dummy_tool)
async def test_execute_tool_pydantic_validation_error(mock_get_tool: AsyncMock, engine: AgentEngine) -> None:
    """Ensures LLM hallucinations (bad data types) are caught and stringified."""
    # Arrange: LLM hallucinates a string instead of an int
    args = {"order_id": "one hundred twenty three"}

    # Act
    result = await engine._execute_tool("dummy_action", args, user_id=42)

    # Assert: Pydantic should trap this before the python function runs
    assert "Action Failed" in result
    assert "validation error" in result.lower()


@pytest.mark.asyncio
async def test_run_direct_response(engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine returns immediately if the LLM doesn't call a tool."""
    # Arrange: LLM just wants to talk
    mock_llm.chat.return_value = Message(
        role="assistant",
        content="Hello! How can I help you today?",
        tool_calls=None
    )

    # Act
    result = await engine.run(user_prompt="Hi", user_id=42)

    # Assert
    assert result == "Hello! How can I help you today?"
    assert mock_llm.chat.call_count == 1


@pytest.mark.asyncio
@patch("agent_api.agent.engine.AgentEngine._execute_tool", return_value="Tool execution was successful.")
async def test_run_with_tool_call(mock_execute: AsyncMock, engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine executes tools and feeds the observation back to the LLM."""
    # Arrange 1st Loop: LLM decides to call a tool
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
    # Arrange 2nd Loop: LLM reads the tool output and provides a final answer
    msg2 = Message(
        role="assistant",
        content="I have successfully processed your order."
    )
    mock_llm.chat.side_effect = [msg1, msg2]

    # Act
    result = await engine.run(user_prompt="Process order 1", user_id=42)

    # Assert
    assert result == "I have successfully processed your order."
    assert mock_llm.chat.call_count == 2
    mock_execute.assert_called_once_with(
        tool_name="dummy_action",
        arguments={"order_id": 1},
        user_id=42
    )


@pytest.mark.asyncio
async def test_run_max_loops_exceeded(engine: AgentEngine, mock_llm: AsyncMock) -> None:
    """Ensures the engine aborts if the LLM gets stuck in an infinite tool-calling loop."""
    # Lower the limit to speed up the test
    engine.max_loops = 2

    # Arrange: LLM stubbornly keeps calling a tool over and over without ever returning a message
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

    # Act
    with patch("agent_api.agent.engine.AgentEngine._execute_tool", return_value="Result"):
        result = await engine.run(user_prompt="Do something", user_id=42)

    # Assert
    assert "complex issue and need to stop" in result
    assert mock_llm.chat.call_count == 2