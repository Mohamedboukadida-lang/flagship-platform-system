"""Tenant isolation at the database (spec section 6). Runs on every pull request.

Everything here connects as lotse_app or lotse_platform, the roles the API uses.
"""

from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from lotse.core import db
from lotse.settings import Settings

from ..conftest import APP_PASSWORD, PLATFORM_PASSWORD, TEST_DB, World, dsn


@pytest.fixture
async def engine(settings: Settings, database: str) -> AsyncIterator[AsyncEngine]:
    engine = db.create_engine(settings.database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return db.create_session_factory(engine)


@pytest.fixture
async def app_conn(database: str) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(dsn("lotse_app", APP_PASSWORD, TEST_DB))
    yield conn
    await conn.close()


async def test_tenant_session_sees_only_its_own_rows(
    sessions: async_sessionmaker[AsyncSession], world: World
) -> None:
    async with db.tenant_session_for(sessions, world.tenant_a, world.alice) as session:
        rows = (await session.execute(text("SELECT tenant_id, user_id FROM memberships"))).all()
    assert {r.user_id for r in rows} == {world.alice, world.adam}
    assert {r.tenant_id for r in rows} == {world.tenant_a}


async def test_guessing_another_tenants_ids_returns_nothing(
    sessions: async_sessionmaker[AsyncSession], world: World
) -> None:
    async with db.tenant_session_for(sessions, world.tenant_a, world.alice) as session:
        by_tenant = await session.execute(
            text("SELECT 1 FROM memberships WHERE tenant_id = :t"), {"t": world.tenant_b}
        )
        by_user = await session.execute(
            text("SELECT 1 FROM memberships WHERE user_id = :u"), {"u": world.bob}
        )
        assert by_tenant.all() == []
        assert by_user.all() == []


async def test_writes_cannot_cross_tenants(
    sessions: async_sessionmaker[AsyncSession], world: World, admin: asyncpg.Connection
) -> None:
    with pytest.raises(DBAPIError, match="row-level security"):
        async with db.tenant_session_for(sessions, world.tenant_a, world.alice) as session:
            await session.execute(
                text("INSERT INTO memberships (tenant_id, user_id, role) VALUES (:t, :u, 'admin')"),
                {"t": world.tenant_b, "u": world.alice},
            )
    async with db.tenant_session_for(sessions, world.tenant_a, world.alice) as session:
        updated = await session.execute(
            text("UPDATE memberships SET role = 'member' WHERE user_id = :u"), {"u": world.bob}
        )
        deleted = await session.execute(
            text("DELETE FROM memberships WHERE tenant_id = :t"), {"t": world.tenant_b}
        )
        assert updated.rowcount == 0
        assert deleted.rowcount == 0
    assert (
        await admin.fetchval("SELECT role FROM memberships WHERE user_id = $1", world.bob)
        == "admin"
    )


async def test_no_tenant_context_reads_zero_rows(
    app_conn: asyncpg.Connection, world: World
) -> None:
    assert await app_conn.fetchval("SELECT count(*) FROM memberships") == 0


async def test_context_does_not_leak_to_the_next_user_of_a_pooled_connection(
    settings: Settings, world: World
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    sessions = db.create_session_factory(engine)
    try:
        async with db.tenant_session_for(sessions, world.tenant_a, world.alice) as session:
            pid = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            assert (
                await session.execute(text("SELECT count(*) FROM memberships"))
            ).scalar_one() == 2
        async with sessions() as session:
            assert (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one() == pid
            assert (await session.execute(text("SELECT app_tenant()"))).scalar_one() is None
            assert (
                await session.execute(text("SELECT count(*) FROM memberships"))
            ).scalar_one() == 0
    finally:
        await engine.dispose()


async def test_commit_inside_a_tenant_session_ends_the_context(
    sessions: async_sessionmaker[AsyncSession], world: World
) -> None:
    async with sessions() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(world.tenant_a)}
        )
        assert (await session.execute(text("SELECT count(*) FROM memberships"))).scalar_one() == 2
        await session.commit()
        assert (await session.execute(text("SELECT count(*) FROM memberships"))).scalar_one() == 0


@pytest.mark.parametrize(
    "statement",
    [
        "SET ROLE lotse_owner",
        "SET ROLE postgres",
        "ALTER TABLE memberships DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY",
        "DROP POLICY tenant_isolation ON memberships",
        "CREATE POLICY open ON memberships USING (true)",
        "SELECT * FROM pg_authid",
        "SELECT * FROM tenants",
        "SELECT * FROM users",
        "SELECT * FROM get_user('00000000-0000-0000-0000-000000000000')",
        "SELECT * FROM list_user_tenants('00000000-0000-0000-0000-000000000000')",
        "SELECT * FROM resolve_membership(gen_random_uuid(), 'sub-bob', '', '', 'tenant-b')",
        "CREATE TABLE loot (id int)",
    ],
)
async def test_app_role_cannot_escape(
    app_conn: asyncpg.Connection, world: World, statement: str
) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app_conn.execute(statement)


async def test_platform_role_reaches_only_its_functions(database: str, world: World) -> None:
    conn = await asyncpg.connect(dsn("lotse_platform", PLATFORM_PASSWORD, TEST_DB))
    try:
        for table in ("tenants", "users", "memberships"):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(f"SELECT * FROM {table}")
        rows = await conn.fetch("SELECT * FROM list_user_tenants($1)", world.bob)
        assert [r["slug"] for r in rows] == ["tenant-b"]
    finally:
        await conn.close()


async def test_runtime_roles_have_no_bypass(admin: asyncpg.Connection) -> None:
    rows = await admin.fetch(
        "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles "
        "WHERE rolname IN ('lotse_app', 'lotse_platform', 'lotse_owner')"
    )
    assert len(rows) == 3
    for row in rows:
        assert not any(row[1:]), dict(row)
    assert not await admin.fetchval(
        "SELECT rolcanlogin FROM pg_roles WHERE rolname = 'lotse_owner'"
    )


async def assert_tenant_tables_protected(admin: asyncpg.Connection) -> None:
    """Every table with a tenant_id column has forced RLS and the tenant_isolation policy."""
    tables = await admin.fetch(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
        """
    )
    assert {t["relname"] for t in tables} >= {"memberships"}
    for table in tables:
        name = table["relname"]
        assert table["relrowsecurity"], f"{name}: row-level security is not enabled"
        assert table["relforcerowsecurity"], f"{name}: row-level security is not forced"
        policies = await admin.fetch(
            "SELECT policyname, roles::text[] AS roles, qual, with_check FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = $1",
            name,
        )
        by_name = {p["policyname"]: p for p in policies}
        assert "tenant_isolation" in by_name, f"{name}: no tenant_isolation policy"
        isolation = by_name["tenant_isolation"]
        assert isolation["qual"] == "(tenant_id = app_tenant())", name
        assert isolation["with_check"] == "(tenant_id = app_tenant())", name
        # Any other policy may only serve the NOLOGIN owner, never a runtime role.
        for policy in policies:
            if policy["policyname"] != "tenant_isolation":
                assert policy["roles"] == ["lotse_owner"], f"{name}: {policy['policyname']}"


async def test_every_tenant_table_is_protected(admin: asyncpg.Connection) -> None:
    await assert_tenant_tables_protected(admin)


ISOLATION = "USING (tenant_id = app_tenant()) WITH CHECK (tenant_id = app_tenant())"


@pytest.mark.parametrize(
    ("setup", "complaint"),
    [
        ([], "not enabled"),
        (["ALTER TABLE sneaky ENABLE ROW LEVEL SECURITY"], "not forced"),
        (
            [
                "ALTER TABLE sneaky ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE sneaky FORCE ROW LEVEL SECURITY",
            ],
            "no tenant_isolation policy",
        ),
        (
            [
                "ALTER TABLE sneaky ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE sneaky FORCE ROW LEVEL SECURITY",
                f"CREATE POLICY tenant_isolation ON sneaky {ISOLATION}",
                "CREATE POLICY also_everyone ON sneaky USING (true)",
            ],
            "also_everyone",
        ),
    ],
    ids=["no-rls", "not-forced", "no-policy", "extra-open-policy"],
)
async def test_the_gate_catches_an_unprotected_table(
    admin: asyncpg.Connection, setup: list[str], complaint: str
) -> None:
    """The check above must fail for a new tenant table that is not fully protected."""
    await admin.execute("CREATE TABLE sneaky (id int, tenant_id uuid)")
    try:
        for statement in setup:
            await admin.execute(statement)
        with pytest.raises(AssertionError, match=complaint):
            await assert_tenant_tables_protected(admin)
    finally:
        await admin.execute("DROP TABLE sneaky")
