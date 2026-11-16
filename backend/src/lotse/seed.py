"""Seed the two demo tenants and their members. Idempotent: `python -m lotse.seed`.

Runs as the admin role (the migrations URL), which bypasses row-level security.
Synthetic data only.
"""

import asyncio

from sqlalchemy import text

from lotse.core import db
from lotse.core.ids import new_id
from lotse.settings import MigrationSettings

DEMO_TENANTS = [("acme", "Acme GmbH"), ("globex", "Globex AG")]

# oidc_sub must equal the user id in deploy/helm/lotse/files/lotse-realm.json
# (checked by backend/tests/unit/test_seed.py).
DEMO_USERS = [
    ("6f1c8a52-3b0e-4d7a-9c41-2e5f7a1b0c01", "alice@acme.example", "Alice Admin", "acme", "admin"),
    (
        "6f1c8a52-3b0e-4d7a-9c41-2e5f7a1b0c02",
        "bob@acme.example",
        "Bob Approver",
        "acme",
        "approver",
    ),
    (
        "6f1c8a52-3b0e-4d7a-9c41-2e5f7a1b0c03",
        "carol@acme.example",
        "Carol Member",
        "acme",
        "member",
    ),
    (
        "6f1c8a52-3b0e-4d7a-9c41-2e5f7a1b0c04",
        "dave@globex.example",
        "Dave Admin",
        "globex",
        "admin",
    ),
]


async def seed(database_url: str) -> None:
    engine = db.create_engine(database_url)
    try:
        async with engine.begin() as connection:
            for slug, name in DEMO_TENANTS:
                await connection.execute(
                    text(
                        "INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug) "
                        "ON CONFLICT (slug) DO NOTHING"
                    ),
                    {"id": new_id(), "name": name, "slug": slug},
                )
            for sub, email, display_name, slug, role in DEMO_USERS:
                await connection.execute(
                    text(
                        "INSERT INTO users (id, oidc_sub, email, display_name) "
                        "VALUES (:id, :sub, :email, :name) ON CONFLICT (oidc_sub) DO NOTHING"
                    ),
                    {"id": new_id(), "sub": sub, "email": email, "name": display_name},
                )
                await connection.execute(
                    text(
                        "INSERT INTO memberships (tenant_id, user_id, role) "
                        "SELECT t.id, u.id, :role FROM tenants t, users u "
                        "WHERE t.slug = :slug AND u.oidc_sub = :sub "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"role": role, "slug": slug, "sub": sub},
                )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed(MigrationSettings().migrations_database_url))
    print(f"seeded {len(DEMO_TENANTS)} tenants, {len(DEMO_USERS)} users")


if __name__ == "__main__":
    main()
