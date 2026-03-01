import pytest
from pydantic import BaseModel, Field

from agent_api.agent.registry import ToolRegistry


class DummyArgs(BaseModel):
    user_id: int = Field(..., description="The user ID")
    force: bool = Field(default=False, description="Force action")


def test_registry_decorator_and_schema_generation() -> None:
    """Ensures the registry captures tools and generates valid OpenAI JSON schemas."""
    local_registry = ToolRegistry()

    @local_registry.register(args_schema=DummyArgs, name="custom_tool_name")
    async def dummy_tool(user_id: int, force: bool = False) -> str:
        """This is a dummy description for the LLM."""
        return "done"

    tool = local_registry.get_tool("custom_tool_name")
    schemas = local_registry.get_all_schemas()

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


def test_get_tool_returns_none_for_unknown_name() -> None:
    """Ensures get_tool safely returns None for a name not in the registry."""
    local_registry = ToolRegistry()

    assert local_registry.get_tool("nonexistent") is None


def test_get_all_schemas_empty_registry() -> None:
    """Ensures an empty registry returns an empty list of schemas."""
    local_registry = ToolRegistry()

    assert local_registry.get_all_schemas() == []


def test_registry_name_defaults_to_function_name() -> None:
    """Ensures the tool name falls back to the function's __name__ when not provided."""
    local_registry = ToolRegistry()

    @local_registry.register(args_schema=DummyArgs)
    async def my_cool_tool(user_id: int) -> str:
        """My cool tool description."""
        return "cool"

    assert local_registry.get_tool("my_cool_tool") is not None
    assert local_registry.get_tool("my_cool_tool").name == "my_cool_tool"


def test_registry_truncates_docstring_to_first_paragraph() -> None:
    """Ensures only the first paragraph of a multi-paragraph docstring is used."""
    local_registry = ToolRegistry()

    @local_registry.register(args_schema=DummyArgs)
    async def verbose_tool(user_id: int) -> str:
        """Short first paragraph.

        This is a longer second paragraph with implementation details
        that should NOT appear in the tool description sent to the LLM.
        """
        return "verbose"

    tool = local_registry.get_tool("verbose_tool")
    assert tool.description == "Short first paragraph."
    assert "implementation details" not in tool.description


def test_registry_multiple_tools() -> None:
    """Ensures multiple tools can be registered and each produces its own schema."""
    local_registry = ToolRegistry()

    @local_registry.register(args_schema=DummyArgs, name="tool_a")
    async def tool_a(user_id: int) -> str:
        """Tool A."""
        return "a"

    @local_registry.register(args_schema=DummyArgs, name="tool_b")
    async def tool_b(user_id: int) -> str:
        """Tool B."""
        return "b"

    schemas = local_registry.get_all_schemas()
    assert len(schemas) == 2
    names = {s["function"]["name"] for s in schemas}
    assert names == {"tool_a", "tool_b"}

