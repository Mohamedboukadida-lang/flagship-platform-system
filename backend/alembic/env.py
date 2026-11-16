"""Alembic environment. Migrations are hand-written SQL and run as the admin role."""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from lotse.settings import MigrationSettings


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(
        MigrationSettings().migrations_database_url, poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline mode is not supported: migrations need a live database")
asyncio.run(_run_online())
