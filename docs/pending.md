# Pending

What is not done yet, in order. When an item lands on `main`, move it to `docs/progress.md`.

## Decisions needed from the owner

1. **Commit the design spec?** This repo is public. The spec is the build reference, but its build-plan section has personal planning notes (weekly hours, schedule risks, a CV line). Options: commit as is, commit without those notes, or keep it out. Until decided it is supplied per session.
2. **Name.** "Lotse" is a working name. It gets baked into the Python package (`lotse`), the env prefix (`LOTSE_`) and the database roles, so confirm it before the first code.
3. **License.** None yet, which means all rights reserved.
4. **Cost rule for the demo.** The earlier project rule was `terraform destroy` after every session. The spec wants the demo live from week two, with the instance stopped outside demo hours and a budget alarm. Pick one.
5. **Terraform state.** New bootstrap bucket for this project, or reuse an existing one.

## M0 slices (draft, confirm or reorder before starting)

Exit gate: a logged-in request returns the caller's tenant on the public URL; the isolation suite runs in CI.

| # | Slice | Acceptance check |
| --- | --- | --- |
| 1 | Tooling: `pyproject.toml`, `uv.lock`, linter, type-checker, pytest, `Makefile` with `setup` and `check` | `make check` passes on a clean clone |
| 2 | `compose.yaml`: Postgres with pgvector, Redis, MinIO, Keycloak | `make up` brings every service to healthy |
| 3 | `ci.yml`: lint, types, unit tests on every push | Green run on `main` |
| 4 | `core`: settings, typed errors as problem+json, UUIDv7 ids, tracing; `/healthz`, `/readyz` | Unit tests; `/readyz` fails when Postgres is down |
| 5 | Schema baseline: roles, `tenants`, `users`, `memberships`, RLS helpers, Alembic | Isolation tests: no tenant context reads zero rows; a table with `tenant_id` and no policy fails the suite |
| 6 | Auth: Keycloak realm, JWT validation, `Principal`, `GET /v1/me` | Integration test: valid token returns the tenant; wrong tenant returns 403; bad token returns 401 |
| 7 | Images and Helm chart for API and worker | Chart installs on a local cluster; `/readyz` is 200 |
| 8 | Terraform: state bootstrap, network, k3s instance, GitHub OIDC deploy role; `deploy.yml` | `/v1/me` answers on the public URL; no stored AWS keys |
| 9 | ADRs 0001 to 0004 (monolith, RLS tenancy, Keycloak, k3s) | Files in `docs/decisions/` |

## Later milestones

M1 to M8 are listed with dates and exit gates in `docs/progress.md`. Each gets its own slice list here when it starts.

Cut order if time runs short: MCP server, router, semantic cache, memory, forensics diff.

## Repo housekeeping (optional, small)

- Branch protection on `main` once CI exists
- Pull request template
- Secret scanning and Dependabot in the repository settings
