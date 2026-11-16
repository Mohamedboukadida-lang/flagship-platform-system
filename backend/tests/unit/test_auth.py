import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from lotse.core.auth import ROLE_PERMISSIONS, Principal, TokenVerifier
from lotse.core.errors import Forbidden, Unauthorized
from lotse.core.ids import new_id

from ..conftest import AUDIENCE, ISSUER, Jwks


@pytest.fixture
def verifier(jwks: Jwks) -> TokenVerifier:
    return TokenVerifier(jwks_url=jwks.url, issuer=ISSUER, audience=AUDIENCE)


def test_valid_token_returns_claims(verifier: TokenVerifier, jwks: Jwks) -> None:
    claims = verifier.decode(jwks.token("sub-1"))
    assert claims["sub"] == "sub-1"
    assert claims["email"] == "sub-1@example.test"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 60},
        {"aud": "another-api"},
        {"aud": None},
        {"iss": "http://evil.test/realms/lotse"},
        {"sub": None},
        {"sub": ""},
        {"iat": None},
        {"exp": None},
    ],
    ids=["expired", "wrong-aud", "no-aud", "wrong-iss", "no-sub", "empty-sub", "no-iat", "no-exp"],
)
def test_bad_claims_are_rejected(verifier: TokenVerifier, jwks: Jwks, overrides: dict) -> None:
    with pytest.raises(Unauthorized):
        verifier.decode(jwks.token(**overrides))


def test_token_signed_by_another_key_is_rejected(verifier: TokenVerifier, jwks: Jwks) -> None:
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(Unauthorized):
        verifier.decode(jwks.token(key=attacker_key))


def test_symmetric_algorithm_is_rejected(verifier: TokenVerifier, jwks: Jwks) -> None:
    """Algorithm confusion: a token signed with HS256 must never validate."""
    with pytest.raises(Unauthorized):
        verifier.decode(jwks.token(key="x" * 64, alg="HS256"))


def test_unsigned_token_is_rejected(verifier: TokenVerifier) -> None:
    now = int(time.time())
    unsigned = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "s", "iat": now, "exp": now + 60},
        key="",
        algorithm="none",
        headers={"kid": "test-key"},
    )
    with pytest.raises(Unauthorized):
        verifier.decode(unsigned)


def test_garbage_is_rejected(verifier: TokenVerifier) -> None:
    with pytest.raises(Unauthorized):
        verifier.decode("not-a-token")


def test_role_permissions_match_the_spec_table() -> None:
    member, approver, admin = (ROLE_PERMISSIONS[r] for r in ("member", "approver", "admin"))
    assert member == {"chat:use", "runs:create", "documents:read", "documents:write"}
    assert approver - member == {"approvals:decide"}
    assert admin - approver == {
        "datasources:manage",
        "members:manage",
        "budgets:manage",
        "audit:read",
        "tenant:delete",
    }


def test_require_checks_the_permission_not_the_role() -> None:
    principal = Principal(new_id(), new_id(), "member", ROLE_PERMISSIONS["member"])
    principal.require("chat:use")
    with pytest.raises(Forbidden):
        principal.require("approvals:decide")
