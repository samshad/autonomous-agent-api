"""
Shared test fixtures.

• ``real_db_session`` — connects to the **real** Postgres instance configured
  in ``.env`` (via ``DATABASE_URL``).  Every test runs inside a top-level
  transaction that is **rolled back** at teardown, so production data is never
  touched.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from agent_api.core.config import settings

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def real_db_session() -> AsyncSession:  # type: ignore[misc]
    """
    Industry-standard fixture for database isolation.

    1. Opens a connection to the real Postgres.
    2. Starts a top-level transaction.
    3. Yields a session bound to that connection — any ``commit()`` inside
       the test is turned into a nested savepoint.
    4. On teardown the top-level transaction is **rolled back**, so the
       real data is never modified.
    """
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.connect() as conn:
        trans = await conn.begin()

        session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )

        yield session

        await session.close()
        await trans.rollback()

    await engine.dispose()
