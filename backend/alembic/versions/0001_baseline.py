"""Baseline: roles, tenants, users, memberships, row-level security helpers.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# One statement per entry: the asyncpg driver prepares statements one at a time.
UPGRADE = [
    # Roles. Passwords are never set here: the database bootstrap creates the login roles
    # (deploy/helm/lotse/files/init-db.sh). This block only covers a database without them.
    """
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lotse_owner') THEN
        CREATE ROLE lotse_owner NOLOGIN;
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lotse_app') THEN
        CREATE ROLE lotse_app NOLOGIN NOBYPASSRLS;
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lotse_platform') THEN
        CREATE ROLE lotse_platform NOLOGIN NOBYPASSRLS;
      END IF;
    END $$
    """,
    # Current tenant and user from transaction-local settings. NULL when unset, which makes
    # every policy false: a missing tenant context shows zero rows.
    """
    CREATE FUNCTION app_tenant() RETURNS uuid LANGUAGE sql STABLE AS
    $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$
    """,
    """
    CREATE FUNCTION app_user() RETURNS uuid LANGUAGE sql STABLE AS
    $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$
    """,
    # Platform tables: no tenant_id, no grant to lotse_app. Reached only through the
    # SECURITY DEFINER functions below.
    """
    CREATE TABLE tenants (
      id         uuid PRIMARY KEY,
      name       text NOT NULL,
      slug       text NOT NULL UNIQUE
                 CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'),
      status     text NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'suspended', 'deleting')),
      settings   jsonb NOT NULL DEFAULT '{}',
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE users (
      id           uuid PRIMARY KEY,
      oidc_sub     text NOT NULL UNIQUE,
      email        text NOT NULL DEFAULT '',
      display_name text NOT NULL DEFAULT '',
      created_at   timestamptz NOT NULL DEFAULT now(),
      updated_at   timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE memberships (
      tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
      user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role       text NOT NULL CHECK (role IN ('admin', 'approver', 'member')),
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (tenant_id, user_id)
    )
    """,
    "CREATE INDEX memberships_user ON memberships (user_id)",
    "ALTER TABLE memberships ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE memberships FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY tenant_isolation ON memberships
      USING (tenant_id = app_tenant()) WITH CHECK (tenant_id = app_tenant())
    """,
    # FORCE applies policies to the table owner too. The owner is NOLOGIN and is only ever
    # the executing role inside the SECURITY DEFINER functions, which must find a membership
    # before any tenant context exists.
    "CREATE POLICY platform_read ON memberships FOR SELECT TO lotse_owner USING (true)",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON memberships TO lotse_app",
    # Upsert the user by oidc_sub (first login creates it), then return the membership for
    # the requested tenant, or no row. The user row is written only when something changed.
    """
    CREATE FUNCTION resolve_membership(
      p_new_user_id uuid, p_sub text, p_email text, p_display_name text, p_tenant_slug text
    ) RETURNS TABLE (user_id uuid, tenant_id uuid, role text)
    LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      WITH written AS (
        INSERT INTO users AS u (id, oidc_sub, email, display_name)
        VALUES (p_new_user_id, p_sub, p_email, p_display_name)
        ON CONFLICT (oidc_sub) DO UPDATE
          SET email = EXCLUDED.email, display_name = EXCLUDED.display_name, updated_at = now()
          WHERE u.email IS DISTINCT FROM EXCLUDED.email
             OR u.display_name IS DISTINCT FROM EXCLUDED.display_name
        RETURNING u.id
      ), caller AS (
        SELECT w.id FROM written w
        UNION ALL
        SELECT u.id FROM users u
        WHERE u.oidc_sub = p_sub AND NOT EXISTS (SELECT 1 FROM written)
      )
      SELECT m.user_id, m.tenant_id, m.role
      FROM caller c
      JOIN memberships m ON m.user_id = c.id
      JOIN tenants t ON t.id = m.tenant_id
      WHERE t.slug = p_tenant_slug AND t.status = 'active'
    $$
    """,
    """
    CREATE FUNCTION list_user_tenants(p_user_id uuid)
    RETURNS TABLE (tenant_id uuid, slug text, name text, role text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      SELECT t.id, t.slug, t.name, m.role
      FROM memberships m JOIN tenants t ON t.id = m.tenant_id
      WHERE m.user_id = p_user_id AND t.status = 'active'
      ORDER BY t.slug
    $$
    """,
    """
    CREATE FUNCTION get_user(p_user_id uuid)
    RETURNS TABLE (id uuid, email text, display_name text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      SELECT u.id, u.email, u.display_name FROM users u WHERE u.id = p_user_id
    $$
    """,
    "ALTER TABLE tenants OWNER TO lotse_owner",
    "ALTER TABLE users OWNER TO lotse_owner",
    "ALTER TABLE memberships OWNER TO lotse_owner",
    "ALTER FUNCTION resolve_membership(uuid, text, text, text, text) OWNER TO lotse_owner",
    "ALTER FUNCTION list_user_tenants(uuid) OWNER TO lotse_owner",
    "ALTER FUNCTION get_user(uuid) OWNER TO lotse_owner",
    # Functions are executable by PUBLIC unless revoked.
    "REVOKE ALL ON FUNCTION resolve_membership(uuid, text, text, text, text) FROM PUBLIC",
    "REVOKE ALL ON FUNCTION list_user_tenants(uuid) FROM PUBLIC",
    "REVOKE ALL ON FUNCTION get_user(uuid) FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION resolve_membership(uuid, text, text, text, text) TO lotse_platform",
    "GRANT EXECUTE ON FUNCTION list_user_tenants(uuid) TO lotse_platform",
    "GRANT EXECUTE ON FUNCTION get_user(uuid) TO lotse_platform",
]

# Roles are cluster-wide and may be shared with other databases, so they stay.
DOWNGRADE = [
    "DROP FUNCTION get_user(uuid)",
    "DROP FUNCTION list_user_tenants(uuid)",
    "DROP FUNCTION resolve_membership(uuid, text, text, text, text)",
    "DROP TABLE memberships",
    "DROP TABLE users",
    "DROP TABLE tenants",
    "DROP FUNCTION app_user()",
    "DROP FUNCTION app_tenant()",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
