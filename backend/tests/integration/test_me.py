import asyncpg
import httpx

from ..conftest import Jwks, World


def auth(token: str, tenant: str | None = "tenant-a") -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant is not None:
        headers["X-Tenant"] = tenant
    return headers


async def test_member_gets_their_tenant_role_and_permissions(
    client: httpx.AsyncClient, jwks: Jwks, world: World
) -> None:
    response = await client.get("/v1/me", headers=auth(jwks.token("sub-adam")))
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == str(world.adam)
    assert body["tenant"] == {"id": str(world.tenant_a), "slug": "tenant-a", "name": "Tenant"}
    assert body["role"] == "member"
    assert body["permissions"] == ["chat:use", "documents:read", "documents:write", "runs:create"]
    assert body["tenants"] == [
        {"id": str(world.tenant_a), "slug": "tenant-a", "name": "Tenant", "role": "member"}
    ]


async def test_admin_has_admin_permissions(
    client: httpx.AsyncClient, jwks: Jwks, world: World
) -> None:
    body = (await client.get("/v1/me", headers=auth(jwks.token("sub-alice")))).json()
    assert body["role"] == "admin"
    assert "tenant:delete" in body["permissions"]


async def test_user_in_two_tenants_sees_both_and_the_requested_one_is_current(
    client: httpx.AsyncClient, jwks: Jwks, world: World, admin: asyncpg.Connection
) -> None:
    await admin.execute(
        "INSERT INTO memberships (tenant_id, user_id, role) VALUES ($1, $2, 'approver')",
        world.tenant_b,
        world.alice,
    )
    body = (await client.get("/v1/me", headers=auth(jwks.token("sub-alice"), "tenant-b"))).json()
    assert body["tenant"]["slug"] == "tenant-b"
    assert body["role"] == "approver"
    assert [(t["slug"], t["role"]) for t in body["tenants"]] == [
        ("tenant-a", "admin"),
        ("tenant-b", "approver"),
    ]


async def test_profile_follows_the_token_claims(
    client: httpx.AsyncClient, jwks: Jwks, world: World
) -> None:
    token = jwks.token("sub-adam", email="new@example.test", name="Adam Renamed")
    body = (await client.get("/v1/me", headers=auth(token))).json()
    assert body["user"]["email"] == "new@example.test"
    assert body["user"]["display_name"] == "Adam Renamed"


async def test_first_login_creates_the_user_but_grants_nothing(
    client: httpx.AsyncClient, jwks: Jwks, world: World, admin: asyncpg.Connection
) -> None:
    response = await client.get("/v1/me", headers=auth(jwks.token("sub-newcomer")))
    assert response.status_code == 403
    assert await admin.fetchval("SELECT count(*) FROM users WHERE oidc_sub = 'sub-newcomer'") == 1
    assert await admin.fetchval("SELECT count(*) FROM memberships") == 3


async def test_repeated_logins_do_not_rewrite_an_unchanged_user(
    client: httpx.AsyncClient, jwks: Jwks, world: World, admin: asyncpg.Connection
) -> None:
    token = jwks.token("sub-adam", email="adam@example.test", name="Adam")
    before = await admin.fetchval("SELECT xmin::text FROM users WHERE oidc_sub = 'sub-adam'")
    for _ in range(2):
        assert (await client.get("/v1/me", headers=auth(token))).status_code == 200
    after = await admin.fetchval("SELECT xmin::text FROM users WHERE oidc_sub = 'sub-adam'")
    assert before == after


async def test_other_tenant_and_unknown_tenant_get_the_same_403(
    client: httpx.AsyncClient, jwks: Jwks, world: World
) -> None:
    token = jwks.token("sub-adam")
    other = await client.get("/v1/me", headers=auth(token, "tenant-b"))
    unknown = await client.get("/v1/me", headers=auth(token, "no-such-tenant"))
    malformed = await client.get("/v1/me", headers=auth(token, "Not A Slug!"))
    assert other.status_code == unknown.status_code == malformed.status_code == 403

    def visible(response: httpx.Response) -> dict:
        return {k: v for k, v in response.json().items() if k != "trace_id"}

    assert visible(other) == visible(unknown) == visible(malformed)


async def test_suspended_tenant_is_not_accessible(
    client: httpx.AsyncClient, jwks: Jwks, world: World, admin: asyncpg.Connection
) -> None:
    await admin.execute("UPDATE tenants SET status = 'suspended' WHERE slug = 'tenant-a'")
    response = await client.get("/v1/me", headers=auth(jwks.token("sub-adam")))
    assert response.status_code == 403


async def test_missing_or_invalid_token_is_401_before_anything_else(
    client: httpx.AsyncClient, jwks: Jwks, world: World
) -> None:
    assert (await client.get("/v1/me")).status_code == 401
    assert (await client.get("/v1/me", headers={"X-Tenant": "tenant-a"})).status_code == 401
    expired = jwks.token("sub-adam", exp=1)
    assert (await client.get("/v1/me", headers=auth(expired))).status_code == 401
    assert (await client.get("/v1/me", headers=auth("garbage"))).status_code == 401


async def test_missing_tenant_header_is_400(
    client: httpx.AsyncClient, jwks: Jwks, world: World
) -> None:
    response = await client.get("/v1/me", headers=auth(jwks.token("sub-adam"), tenant=None))
    assert response.status_code == 400
    assert response.json()["detail"] == "X-Tenant header is required"
