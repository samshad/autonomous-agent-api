"""
core/database.py - SQLAlchemy AsyncEngine & session management.

Provides DatabaseManager, a context manager that owns
the engine lifecycle and hands out AsyncSession objects via an
async context-manager helper.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """Owns the async SQLAlchemy engine and session factory.

    Usage::

        db = DatabaseManager(database_url="postgresql+asyncpg://...")
        async with db.session() as session:
            result = await session.execute(...)
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
        pool_max_overflow: int = 10,
        pool_recycle_seconds: int = 300,
    ) -> None:
        # SQLite (used in tests) does not support pool configuration
        is_sqlite = database_url.startswith("sqlite")
        pool_kwargs: dict = {} if is_sqlite else {
            "pool_size": pool_size,
            "pool_max_overflow": pool_max_overflow,
            "pool_recycle": pool_recycle_seconds,
        }

        self._engine: AsyncEngine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,
            **pool_kwargs,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Yields an asynchronous database session.
        Automatically handles transaction rollbacks if an exception bubbles up,
        and ensures the connection is returned to the pool.
        """
        async with self._session_factory() as session:
            try:
                yield session
            except Exception as e:
                logger.error("database_session_error", error=str(e), exc_info=True)
                await session.rollback()
                raise

    async def dispose(self) -> None:
        """Disposes of the connection pool gracefully during app shutdown."""
        await self._engine.dispose()
        logger.info("database_engine_disposed")
