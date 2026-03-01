from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.agent.engine import AgentEngine
from agent_api.agent.llm_client import OllamaClient
from agent_api.repository.order_repo import OrderRepository
from agent_api.services.commerce import CommerceService

logger = structlog.get_logger(__name__)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an active database session mapped to the current request.
    Automatically commits on success, and rolls back on failure (Unit of Work).
    """
    db_manager = request.app.state.db_manager
    async with db_manager.session() as session:
        try:
            yield session
            await session.commit()
            logger.info("db_session_commit")
        except Exception as e:
            logger.error("db_session_rollback", error=str(e))
            await session.rollback()
            raise


async def get_agent_engine(session: AsyncSession = Depends(get_db_session)) -> AgentEngine:
    """
    Assembles the AI Orchestration layer and Domain Services for the current request.
    """
    # 1. Data Access Layer
    repo = OrderRepository(session=session)

    # 2. Business Logic Layer
    service = CommerceService(order_repo=repo)

    # 3. Infrastructure (LLM API)
    llm_client = OllamaClient()

    # 4. Orchestrator
    return AgentEngine(llm_client=llm_client, commerce_service=service)
