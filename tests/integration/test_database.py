import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_database_manager_yields_active_session(real_db_session: AsyncSession) -> None:
    """
    Ensures the real Postgres connection is active and functional.
    Uses the transactional ``real_db_session`` fixture so nothing is persisted.
    """
    assert isinstance(real_db_session, AsyncSession)
    assert real_db_session.is_active is True

    # Prove we can execute a trivial query against the real DB
    result = await real_db_session.execute(
        __import__("sqlalchemy").text("SELECT 1")
    )
    assert result.scalar() == 1
