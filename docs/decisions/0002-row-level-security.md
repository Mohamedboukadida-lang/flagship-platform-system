# 0002: Shared schema with row-level security for tenancy

Status: accepted, 2026-11-16 (M0)

## Decision

All tenants share one schema. Every tenant-owned table has a `tenant_id` column and a forced row-level security policy `tenant_isolation`: `tenant_id = app_tenant()`, for reads and writes. `app_tenant()` reads a transaction-local setting that is set in exactly one place, `lotse.core.db.tenant_session_for`.

Three database roles:

| Role | Login | Can do |
| --- | --- | --- |
| `lotse_owner` | no | Owns tables and functions |
| `lotse_app` | yes | Tenant tables, always filtered by the policy. No access to `tenants` or `users` |
| `lotse_platform` | yes | Executes three `SECURITY DEFINER` functions: `resolve_membership`, `list_user_tenants`, `get_user` |

None of them can bypass row-level security. Login roles get their passwords from the database bootstrap (`deploy/helm/lotse/files/init-db.sh`), never from a migration.

## Why

Isolation that survives application bugs: a query that forgets its `WHERE tenant_id` returns nothing instead of another tenant's rows. One schema keeps migrations and operations simple.

## Alternatives

- Schema or database per tenant: stronger separation, but migrations and connection pools multiply with tenants.
- Filtering in application code only: one missed filter is a data leak.

## Details worth knowing

- With no tenant context, `app_tenant()` is NULL, every policy is false, and the session sees zero rows. A commit inside a tenant session ends the context the same way.
- `FORCE ROW LEVEL SECURITY` applies policies to the table owner too. The membership lookup has to run before any tenant context exists, so `memberships` carries a second policy, `platform_read`, for `lotse_owner` only. That role cannot log in; it is only ever the executing role inside the `SECURITY DEFINER` functions.
- The application role is trusted to set the tenant context. Row-level security protects against mistakes in queries, not against a fully compromised API process.

## How it is enforced

`backend/tests/isolation/` runs on every push. It connects as the runtime roles and checks that tenants cannot read or write each other's rows, that the roles cannot escape (`SET ROLE`, disabling RLS, reading `pg_authid`), and that every table with a `tenant_id` column has forced RLS with exactly the expected policy. Four tests plant an unprotected table and assert that the check fails.

## Consequences

Every new tenant table ships with its policy in the same migration, or the suite fails. Superuser connections (migrations, seed) bypass row-level security and must stay out of request paths.
