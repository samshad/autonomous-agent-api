import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from agent_api.core.config import settings

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def real_db_session() -> AsyncSession:  # type: ignore
    """
    Industry-standard test fixture for database isolation.
    Connects to the real database, starts a top-level transaction, and yields a session.
    Any commits inside the test become nested savepoints.
    When the test ends, the top-level transaction is rolled back, leaving the DB untouched.
    """
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.connect() as conn:
        # Start a top-level transaction
        trans = await conn.begin()

        # Bind the session to the connection, turning commits into savepoints
        async_session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False
        )

        yield async_session

        # Teardown: Close the session and rollback the top-level transaction
        await async_session.close()
        await trans.rollback()

    await engine.dispose()
