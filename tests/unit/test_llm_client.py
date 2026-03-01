"""Unit tests for agent_api.agent.llm_client.OllamaClient."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agent_api.agent.llm_client import OllamaClient
from agent_api.models.agent import Message


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def client(mock_http_client: AsyncMock) -> OllamaClient:
    return OllamaClient(
        http_client=mock_http_client,
        base_url="http://localhost:11434",
        model="test-model",
    )


@pytest.mark.asyncio
async def test_chat_sends_correct_payload(client: OllamaClient, mock_http_client: AsyncMock) -> None:
    """Ensures the client builds the correct HTTP payload for Ollama."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"role": "assistant", "content": "Hello!"}
    }
    mock_response.raise_for_status = MagicMock()
    mock_http_client.post.return_value = mock_response

    messages = [Message(role="user", content="Hi")]
    result = await client.chat(messages=messages)

    assert result.role == "assistant"
    assert result.content == "Hello!"

    # Verify the POST was sent to the correct URL
    call_args = mock_http_client.post.call_args
    assert call_args[0][0] == "http://localhost:11434/api/chat"

    # Verify the payload structure
    payload = call_args[1]["json"]
    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    assert len(payload["messages"]) == 1
    assert "tools" not in payload


@pytest.mark.asyncio
async def test_chat_includes_tools_when_provided(client: OllamaClient, mock_http_client: AsyncMock) -> None:
    """Ensures tools are included in the payload when passed."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"role": "assistant", "content": "OK"}}
    mock_response.raise_for_status = MagicMock()
    mock_http_client.post.return_value = mock_response

    tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
    await client.chat(messages=[Message(role="user", content="Hi")], tools=tools)

    payload = mock_http_client.post.call_args[1]["json"]
    assert payload["tools"] == tools


@pytest.mark.asyncio
async def test_chat_omits_tools_when_none(client: OllamaClient, mock_http_client: AsyncMock) -> None:
    """Ensures tools key is absent from payload when tools=None."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"role": "assistant", "content": "OK"}}
    mock_response.raise_for_status = MagicMock()
    mock_http_client.post.return_value = mock_response

    await client.chat(messages=[Message(role="user", content="Hi")], tools=None)

    payload = mock_http_client.post.call_args[1]["json"]
    assert "tools" not in payload


@pytest.mark.asyncio
async def test_chat_raises_runtime_error_on_http_failure(
    client: OllamaClient, mock_http_client: AsyncMock
) -> None:
    """Ensures HTTP errors are wrapped in RuntimeError with a descriptive message."""
    mock_http_client.post.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(RuntimeError, match="Failed to communicate with LLM"):
        await client.chat(messages=[Message(role="user", content="Hi")])


@pytest.mark.asyncio
async def test_chat_raises_on_http_status_error(
    client: OllamaClient, mock_http_client: AsyncMock
) -> None:
    """Ensures non-2xx HTTP status codes raise RuntimeError."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=MagicMock(),
        response=MagicMock(),
    )
    mock_http_client.post.return_value = mock_response

    with pytest.raises(RuntimeError, match="Failed to communicate with LLM"):
        await client.chat(messages=[Message(role="user", content="Hi")])


@pytest.mark.asyncio
async def test_chat_handles_missing_message_key_gracefully(
    client: OllamaClient, mock_http_client: AsyncMock
) -> None:
    """Ensures a response with no 'message' key doesn't crash with a confusing error."""
    mock_response = MagicMock()
    mock_response.json.return_value = {}  # No "message" key at all
    mock_response.raise_for_status = MagicMock()
    mock_http_client.post.return_value = mock_response

    # data.get("message", {}) returns {} → Message(**{}) → ValidationError
    with pytest.raises(Exception):
        await client.chat(messages=[Message(role="user", content="Hi")])


@pytest.mark.asyncio
async def test_base_url_trailing_slash_is_normalized() -> None:
    """Ensures trailing slashes in base_url don't cause double-slash in URL."""
    client = OllamaClient(
        http_client=AsyncMock(spec=httpx.AsyncClient),
        base_url="http://localhost:11434/",
        model="test",
    )
    assert client.base_url == "http://localhost:11434/api"


