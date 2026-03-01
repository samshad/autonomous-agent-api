import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_api.core.database import DatabaseManager


@pytest.mark.asyncio
async def test_database_manager_yields_active_session() -> None:
    """
    Ensures the DatabaseManager correctly initializes the SQLAlchemy async engine
    and yields a functional AsyncSession.
    """
    # Arrange: Initialize the manager with a dummy test SQLite URL for isolation,
    # though eventually we will use a test Postgres DB.
    # We use sqlite+aiosqlite for the absolute simplest initial connection test,
    # but we will migrate to asyncpg + postgres in the next step.
    test_db_url = "sqlite+aiosqlite:///:memory:"
    db_manager = DatabaseManager(database_url=test_db_url)

    # Act: Attempt to get a session
    async with db_manager.session() as session:
        # Assert: Verify the session is the correct type and is active
        assert isinstance(session, AsyncSession)
        assert session.is_active is True
