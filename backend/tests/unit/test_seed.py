import json
from pathlib import Path

from lotse.seed import DEMO_TENANTS, DEMO_USERS

REALM = Path(__file__).resolve().parents[3] / "deploy/helm/lotse/files/lotse-realm.json"


def test_seed_users_match_the_keycloak_realm() -> None:
    realm_users = {u["id"]: u["email"] for u in json.loads(REALM.read_text())["users"]}
    seed_users = {sub: email for sub, email, *_ in DEMO_USERS}
    assert seed_users == realm_users


def test_every_seed_user_belongs_to_a_seeded_tenant() -> None:
    slugs = {slug for slug, _ in DEMO_TENANTS}
    assert {tenant for *_, tenant, _role in DEMO_USERS} <= slugs


def test_realm_file_holds_no_literal_password() -> None:
    for user in json.loads(REALM.read_text())["users"]:
        for credential in user["credentials"]:
            assert credential["value"] == "${LOTSE_DEMO_PASSWORD}"
