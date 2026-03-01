import pytest
from pydantic import BaseModel, Field

from agent_api.agent.registry import ToolRegistry


class DummyArgs(BaseModel):
    user_id: int = Field(..., description="The user ID")
    force: bool = Field(default=False, description="Force action")


def test_registry_decorator_and_schema_generation() -> None:
    """Ensures the registry captures tools and generates valid OpenAI JSON schemas."""
    # Arrange
    local_registry = ToolRegistry()

    @local_registry.register(args_schema=DummyArgs, name="custom_tool_name")
    async def dummy_tool(user_id: int, force: bool = False) -> str:
        """This is a dummy description for the LLM."""
        return "done"

    # Act
    tool = local_registry.get_tool("custom_tool_name")
    schemas = local_registry.get_all_schemas()

    # Assert
    assert tool is not None
    assert tool.name == "custom_tool_name"
    assert tool.description == "This is a dummy description for the LLM."

    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "custom_tool_name"
    assert schema["function"]["description"] == "This is a dummy description for the LLM."

    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert "user_id" in params["properties"]
    assert params["properties"]["user_id"]["description"] == "The user ID"
    assert params["properties"]["user_id"]["type"] == "integer"
    assert "user_id" in params["required"]
    assert "force" not in params["required"]


def test_registry_fails_fast_without_docstring() -> None:
    """Ensures tools without documentation crash immediately at startup."""
    local_registry = ToolRegistry()

    with pytest.raises(ValueError) as exc_info:
        @local_registry.register(args_schema=DummyArgs)
        async def bad_tool(user_id: int) -> str:
            pass  # Missing docstring!

    assert "must have a docstring" in str(exc_info.value)
