"""JWT validation and the request principal (spec section 6). Fails closed."""

import re
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from lotse.core.errors import BadRequest, Forbidden, Unauthorized
from lotse.core.ids import new_id

bearer = HTTPBearer(auto_error=False)

_TENANT_SLUG = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")

_MEMBER = frozenset({"chat:use", "runs:create", "documents:read", "documents:write"})
_APPROVER = _MEMBER | {"approvals:decide"}
_ADMIN = _APPROVER | {
    "datasources:manage",
    "members:manage",
    "budgets:manage",
    "audit:read",
    "tenant:delete",
}
# Endpoints declare the permission they need, never the role.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "member": _MEMBER,
    "approver": _APPROVER,
    "admin": _ADMIN,
}


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    role: str
    permissions: frozenset[str]

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise Forbidden(f"missing permission {permission}")


class TokenVerifier:
    """Validates access tokens against the identity provider's published keys.

    Keys are cached, so validation keeps working if the provider is briefly down.
    """

    def __init__(self, *, jwks_url: str, issuer: str, audience: str) -> None:
        self._jwks = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=600, timeout=5)
        self._issuer = issuer
        self._audience = audience

    def decode(self, token: str) -> dict[str, Any]:
        """Blocking on a key-cache miss (one HTTP call): run it in a thread."""
        try:
            key = self._jwks.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],  # never accept the algorithm from the token
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
                leeway=10,
            )
        except jwt.PyJWTError as exc:
            raise Unauthorized(f"invalid token: {exc}") from exc
        if not isinstance(claims.get("sub"), str) or not 0 < len(claims["sub"]) <= 255:
            raise Unauthorized("invalid token: unusable sub claim")
        return claims


async def get_principal(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    x_tenant: Annotated[str | None, Header(alias="X-Tenant")] = None,
) -> Principal:
    # Order matters: identity first, so an anonymous caller learns nothing but 401.
    if creds is None:
        raise Unauthorized("missing bearer token")
    resources = request.app.state.resources
    claims = await run_in_threadpool(resources.verifier.decode, creds.credentials)

    if x_tenant is None:
        raise BadRequest("missing X-Tenant", public_detail="X-Tenant header is required")
    if not _TENANT_SLUG.fullmatch(x_tenant):
        raise Forbidden("malformed tenant slug")  # same answer as an unknown tenant

    # resolve_membership is SECURITY DEFINER: it upserts the user by oidc_sub and returns
    # the membership for this tenant, or no row.
    display_name = claims.get("name") or claims.get("preferred_username") or ""
    row = await resources.platform_db.fetchrow(
        "SELECT user_id, tenant_id, role FROM resolve_membership($1, $2, $3, $4, $5)",
        new_id(),
        claims["sub"],
        str(claims.get("email", ""))[:320],
        str(display_name)[:200],
        x_tenant,
    )
    if row is None:
        raise Forbidden("not a member of this tenant")  # same answer as an unknown tenant

    principal = Principal(
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        role=row["role"],
        permissions=ROLE_PERMISSIONS[row["role"]],
    )
    request.state.principal = principal
    return principal
