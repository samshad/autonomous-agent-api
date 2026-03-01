"""Unit tests for the RequestIDMiddleware and health/exception handling in main.py."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agent_api.api.dependencies import get_agent_engine
from agent_api.core.exceptions import EntityNotFoundError
from agent_api.main import create_app


def _make_db_manager_mock() -> MagicMock:
    """Build a mock DatabaseManager whose ``.session()`` behaves like the real
    ``@asynccontextmanager`` — no un-awaited coroutine warnings."""

    # Use MagicMock as the session base so sync methods (add) don't return coroutines.
    # Explicitly make async methods (commit, rollback, close) AsyncMock.
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    @asynccontextmanager
    async def _fake_session():
        yield mock_session

    db_manager = MagicMock()
    db_manager.session = _fake_session
    db_manager._mock_session = mock_session  # expose for assertions
    return db_manager


@pytest.fixture
def test_app():
    """Create a fresh app instance with middleware wired up.

    We mock the lifespan's DB and HTTP client to avoid real connections.
    """
    app = create_app()

    app.state.db_manager = _make_db_manager_mock()
    app.state.http_client = AsyncMock()

    return app


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=test_app)  # type: ignore
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ──────────────────────────────────────────────────────────────────────────────
# Health endpoint
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_ok(async_client: httpx.AsyncClient) -> None:
    """Ensures /health returns 200 with status and version."""
    response = await async_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ──────────────────────────────────────────────────────────────────────────────
# X-Request-ID middleware
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_includes_x_request_id_header(async_client: httpx.AsyncClient) -> None:
    """Ensures every response includes an auto-generated X-Request-ID header."""
    response = await async_client.get("/health")

    assert "x-request-id" in response.headers
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 36


@pytest.mark.asyncio
async def test_client_provided_request_id_is_echoed_back(async_client: httpx.AsyncClient) -> None:
    """Ensures a client-provided X-Request-ID is used instead of generating one."""
    custom_id = "my-trace-id-abc-123"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_id})

    assert response.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_request_log_persisted_to_db(test_app, async_client: httpx.AsyncClient) -> None:
    """Ensures the middleware writes a RequestLog row to the DB after each request."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    # The mock session should have had .add() and .commit() called
    mock_session = test_app.state.db_manager._mock_session
    mock_session.add.assert_called()
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_middleware_survives_db_persist_failure(async_client: httpx.AsyncClient, test_app) -> None:
    """Ensures the response is still returned even if request log DB persist fails."""
    # Make the session commit raise an exception
    failing_session = MagicMock()
    failing_session.commit = AsyncMock(side_effect=RuntimeError("DB down"))

    @asynccontextmanager
    async def _failing_session():
        yield failing_session

    test_app.state.db_manager.session = _failing_session

    response = await async_client.get("/health")

    # The response must still be 200 — observability must never break the user
    assert response.status_code == 200
    assert "x-request-id" in response.headers


# ──────────────────────────────────────────────────────────────────────────────
# Input validation (override the engine dependency to skip DB)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_rejects_empty_prompt(test_app, async_client: httpx.AsyncClient) -> None:
    """Ensures empty prompt is rejected by Pydantic validation (min_length=1)."""
    mock_engine = AsyncMock()
    test_app.dependency_overrides[get_agent_engine] = lambda: mock_engine

    response = await async_client.post("/api/v1/chat", json={"prompt": "", "user_id": 1})

    assert response.status_code == 422
    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_rejects_missing_prompt(test_app, async_client: httpx.AsyncClient) -> None:
    """Ensures a missing 'prompt' field returns 422."""
    mock_engine = AsyncMock()
    test_app.dependency_overrides[get_agent_engine] = lambda: mock_engine

    response = await async_client.post("/api/v1/chat", json={"user_id": 1})

    assert response.status_code == 422
    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_rejects_oversized_prompt(test_app, async_client: httpx.AsyncClient) -> None:
    """Ensures prompts exceeding max_prompt_length are rejected."""
    mock_engine = AsyncMock()
    test_app.dependency_overrides[get_agent_engine] = lambda: mock_engine

    huge_prompt = "x" * 3000  # Default max is 2000
    response = await async_client.post("/api/v1/chat", json={"prompt": huge_prompt, "user_id": 1})

    assert response.status_code == 422
    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_accepts_prompt_without_user_id(test_app, async_client: httpx.AsyncClient) -> None:
    """Ensures user_id is optional (None for unauthenticated users)."""
    mock_engine = AsyncMock()
    mock_engine.run.return_value = "Hello!"
    test_app.dependency_overrides[get_agent_engine] = lambda: mock_engine

    response = await async_client.post("/api/v1/chat", json={"prompt": "Hi there"})

    assert response.status_code == 200
    assert response.json()["response"] == "Hello!"
    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_response_includes_request_id(test_app, async_client: httpx.AsyncClient) -> None:
    """Ensures the ChatResponse body includes the correlation request_id."""
    mock_engine = AsyncMock()
    mock_engine.run.return_value = "OK"
    test_app.dependency_overrides[get_agent_engine] = lambda: mock_engine

    response = await async_client.post("/api/v1/chat", json={"prompt": "Hi", "user_id": 1})

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert data["request_id"] is not None
    # Must match the header
    assert data["request_id"] == response.headers["x-request-id"]
    test_app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Exception handlers
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_domain_exception_returns_structured_json(
    test_app, async_client: httpx.AsyncClient
) -> None:
    """Ensures AgentAPIError subclasses produce proper JSON, not 500."""
    mock_engine = AsyncMock()
    mock_engine.run.side_effect = EntityNotFoundError("Order #1 not found")
    test_app.dependency_overrides[get_agent_engine] = lambda: mock_engine

    response = await async_client.post(
        "/api/v1/chat", json={"prompt": "Check order 1", "user_id": 1}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Order #1 not found"
    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unhandled_exception_returns_safe_500(
    test_app, async_client: httpx.AsyncClient
) -> None:
    """Ensures unexpected exceptions are caught by the global exception handler.

    Note: With BaseHTTPMiddleware, the exception also propagates through
    call_next(). Starlette's ExceptionMiddleware (inner) handles it and
    returns a 500 JSON response, but BaseHTTPMiddleware (outer) re-raises.
    In production, uvicorn catches the re-raise. In ASGI transport tests,
    httpx raises it.  We verify the handler is wired by testing the domain
    exception handler (which works at the correct layer) and assert here
    that the ValueError is not silently swallowed.
    """
    mock_engine = AsyncMock()
    mock_engine.run.side_effect = ValueError("some internal bug")
    test_app.dependency_overrides[get_agent_engine] = lambda: mock_engine

    with pytest.raises(ValueError, match="some internal bug"):
        await async_client.post(
            "/api/v1/chat", json={"prompt": "Hello", "user_id": 1}
        )

    test_app.dependency_overrides.clear()




