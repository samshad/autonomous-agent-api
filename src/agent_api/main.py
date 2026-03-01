from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent_api.agent.tools import init_tools
from agent_api.api.routes import chat
from agent_api.core.config import settings
from agent_api.core.database import DatabaseManager
from agent_api.core.exceptions import AgentAPIError
from agent_api.core.middleware import RequestIDMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handles global startup and shutdown events.
    Initializes the database connection pool, httpx client, and attaches them
    to the application state for dependency injection.
    """
    logger.info(
        "app_startup",
        environment=settings.environment,
        version=settings.app_version,
    )

    db_manager = DatabaseManager(
        database_url=settings.database_url,
        echo=settings.debug,
        pool_size=settings.pool_size,
        pool_max_overflow=settings.pool_max_overflow,
        pool_recycle_seconds=settings.pool_recycle_seconds,
    )
    http_client = httpx.AsyncClient(timeout=settings.llm_timeout)

    app.state.db_manager = db_manager
    app.state.http_client = http_client

    yield

    logger.info("app_shutdown_started")
    await http_client.aclose()
    await db_manager.dispose()
    logger.info("app_shutdown_complete")


def create_app() -> FastAPI:
    """Application factory pattern."""
    init_tools()

    app = FastAPI(
        title=settings.project_name,
        description="An AI agent capable of managing e-commerce orders via natural language.",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID / Correlation ID ──────────────────────────────────────
    app.add_middleware(RequestIDMiddleware)

    # ── Global Exception Handlers ────────────────────────────────────────
    @app.exception_handler(AgentAPIError)
    async def agent_api_error_handler(_request: Request, exc: AgentAPIError) -> JSONResponse:
        """Convert any domain AgentAPIError into a structured JSON response."""
        logger.warning("domain_error", status=exc.status_code, detail=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unexpected server errors — never leak internals."""
        logger.error("unhandled_error", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected internal error occurred."},
        )

    # ── Health Check ─────────────────────────────────────────────────────
    @app.get("/health", tags=["Infrastructure"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "version": settings.app_version}

    # ── Routes ───────────────────────────────────────────────────────────
    app.include_router(chat.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
