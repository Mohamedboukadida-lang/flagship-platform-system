"""The only module that opens database connections (enforced by import-linter).

Two roles reach the database at runtime, neither can bypass row-level security:
- lotse_app: tenant tables, always through a tenant-scoped session.
- lotse_platform: a handful of SECURITY DEFINER functions (membership resolution).
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lotse.core.auth import Principal, get_principal


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url, pool_size=10, max_overflow=5, pool_pre_ping=True, pool_recycle=1800
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


@asynccontextmanager
async def tenant_session_for(
    factory: async_sessionmaker[AsyncSession], tenant_id: UUID, user_id: UUID
) -> AsyncIterator[AsyncSession]:
    """One transaction scoped to one tenant. The single place tenant context is set.

    set_config(..., true) is transaction-local: the setting cannot leak to the next user of
    this pooled connection. A commit inside the block ends the context, after which
    row-level security shows zero rows rather than another tenant's.
    """
    async with factory() as session, session.begin():
        await session.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant, true), "
                "set_config('app.user_id', :user, true)"
            ),
            {"tenant": str(tenant_id), "user": str(user_id)},
        )
        yield session


async def tenant_session(
    request: Request, principal: Annotated[Principal, Depends(get_principal)]
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one tenant-scoped transaction per request."""
    factory = request.app.state.resources.session_factory
    async with tenant_session_for(factory, principal.tenant_id, principal.user_id) as session:
        yield session


class PlatformDB:
    """Connection pool for the lotse_platform role."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PlatformDB":
        return cls(await asyncpg.create_pool(dsn, min_size=1, max_size=5, command_timeout=10))

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        row = await self._pool.fetchrow(query, *args)
        return dict(row) if row is not None else None

    async def fetch(self, query: str, *args: object) -> Sequence[Mapping[str, Any]]:
        return [dict(row) for row in await self._pool.fetch(query, *args)]

    async def ping(self) -> None:
        await self._pool.fetchval("SELECT 1")

    async def close(self) -> None:
        await self._pool.close()


def get_platform_db(request: Request) -> PlatformDB:
    platform_db: PlatformDB = request.app.state.resources.platform_db
    return platform_db
