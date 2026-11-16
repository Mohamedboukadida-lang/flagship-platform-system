"""Tenancy logic. Takes a database handle and a Principal; imports no web framework."""

from lotse.core.auth import Principal
from lotse.core.db import PlatformDB
from lotse.core.errors import NotFound
from lotse.modules.tenancy.schemas import MeOut, TenantMembershipOut, TenantOut, UserOut


async def get_me(platform: PlatformDB, principal: Principal) -> MeOut:
    user = await platform.fetchrow(
        "SELECT id, email, display_name FROM get_user($1)", principal.user_id
    )
    rows = await platform.fetch(
        "SELECT tenant_id, slug, name, role FROM list_user_tenants($1)", principal.user_id
    )
    tenants = [
        TenantMembershipOut(id=r["tenant_id"], slug=r["slug"], name=r["name"], role=r["role"])
        for r in rows
    ]
    current = next((t for t in tenants if t.id == principal.tenant_id), None)
    if user is None or current is None:
        # The membership was removed between authentication and this query.
        raise NotFound("user or membership no longer exists")
    return MeOut(
        user=UserOut(id=user["id"], email=user["email"], display_name=user["display_name"]),
        tenant=TenantOut(id=current.id, slug=current.slug, name=current.name),
        role=principal.role,
        permissions=sorted(principal.permissions),
        tenants=tenants,
    )
