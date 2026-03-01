"""Alembic async migration environment.

Reads DATABASE_URL from the application's Settings (which loads .env),
imports every model so autogenerate can detect schema changes, and
runs migrations against the async engine.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from agent_api.core.config import settings
from agent_api.models.domain import Base  # noqa: F401 — registers all models

# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Override the sqlalchemy.url from alembic.ini with the real value from .env
config.set_main_option("sqlalchemy.url", settings.database_url)

# Standard Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The MetaData object that Alembic uses for autogenerate diffing.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against a live database)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
