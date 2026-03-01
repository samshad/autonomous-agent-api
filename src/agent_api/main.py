from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from agent_api.agent.tools import init_tools
from agent_api.api.routes import chat
from agent_api.core.config import settings
from agent_api.core.database import DatabaseManager

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handles global startup and shutdown events.
    Initializes the database connection pool and attaches it to the application state.
    """
    db_manager = DatabaseManager(database_url=settings.database_url)
    app.state.db_manager = db_manager

    yield

    await db_manager.dispose()


def create_app() -> FastAPI:
    """Application factory pattern."""
    init_tools()

    app = FastAPI(
        title="Autonomous AI Agent API",
        description="An AI agent capable of managing e-commerce orders via natural language.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(chat.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
