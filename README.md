# Lotse (working name)

A multi-tenant, privacy-first AI assistant platform. A company signs up, uploads documents and connects a database; its staff ask questions or hand off tasks, and the system answers with citations, guarded SQL and human-approved actions.

## Status

Milestone M0 (walking skeleton) is built and tested locally: a logged-in request returns the caller's tenant, and tenant isolation is enforced by the database and checked on every push. It is not deployed yet; the first deployment is described in [docs/runbooks/demo-deploy.md](docs/runbooks/demo-deploy.md).

- Done so far: [docs/progress.md](docs/progress.md)
- Next steps and what is still unverified: [docs/pending.md](docs/pending.md)

## Run it locally

Needs Docker, [uv](https://docs.astral.sh/uv/) and make.

```bash
make setup
```

```bash
make up
```

```bash
make migrate seed run
```

The API is on `http://localhost:8000` (interactive docs at `/docs`), Keycloak on `http://localhost:8080/auth`. Log in as the demo user `alice` and ask who you are:

```bash
TOKEN=$(curl -s http://localhost:8080/auth/realms/lotse/protocol/openid-connect/token \
  -d grant_type=password -d client_id=lotse-cli -d username=alice -d password=demo_dev \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')
curl -s http://localhost:8000/v1/me -H "Authorization: Bearer $TOKEN" -H "X-Tenant: acme"
```

The same request with `X-Tenant: globex` is refused: `alice` is not a member there.

## What it will do

- Document Q&A where every citation points to a retrieved chunk
- Natural-language questions over a connected PostgreSQL database, read-only and validated
- Agent tasks with tools, where risky actions wait for a recorded human approval
- Tenants, roles, budgets, audit log and data deletion
- Self-hosted or EU-hosted models, switchable per tenant

## Design

| Area | Choice |
| --- | --- |
| Service shape | Modular monolith: one API process, one worker process |
| Store | PostgreSQL 16 with pgvector and full-text search |
| Tenant isolation | Shared schema, `tenant_id` on every table, row-level security |
| Identity | Keycloak (OIDC); the API validates JWTs |
| Background work (M1) | Job table in Postgres with `FOR UPDATE SKIP LOCKED` |
| Agents (M6) | LangGraph with the Postgres checkpointer |
| Frontend (M3) | React, TypeScript, Vite |
| Deployment | Helm on k3s on one EC2 instance, provisioned by Terraform |

## Working in this repo

Rules for contributors and coding agents are in [AGENTS.md](AGENTS.md). The full design is in [docs/system-design.md](docs/system-design.md); the decisions taken so far are in [docs/decisions](docs/decisions).

## License

[MIT](LICENSE)
