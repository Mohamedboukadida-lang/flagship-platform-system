# Lotse (working name)

A multi-tenant, privacy-first AI assistant platform. A company signs up, uploads documents and connects a database; its staff ask questions or hand off tasks, and the system answers with citations, guarded SQL and human-approved actions.

## Status

**Scaffold only.** No runnable code yet. Work starts with milestone M0 (walking skeleton).

- Done so far: [docs/progress.md](docs/progress.md)
- Next steps and open decisions: [docs/pending.md](docs/pending.md)

## What it will do

- Document Q&A where every citation points to a retrieved chunk
- Natural-language questions over a connected PostgreSQL database, read-only and validated
- Agent tasks with tools, where risky actions wait for a recorded human approval
- Tenants, roles, budgets, audit log and data deletion
- Self-hosted or EU-hosted models, switchable per tenant

## Planned design

| Area | Choice |
| --- | --- |
| Service shape | Modular monolith: one API process, one worker process |
| Store | PostgreSQL 16 with pgvector and full-text search |
| Tenant isolation | Shared schema, `tenant_id` on every table, row-level security |
| Identity | Keycloak (OIDC); the API validates JWTs |
| Background work | Job table in Postgres with `FOR UPDATE SKIP LOCKED` |
| Agents | LangGraph with the Postgres checkpointer |
| Frontend | React, TypeScript, Vite |
| Deployment | Helm on k3s on one EC2 instance, provisioned by Terraform |

## Working in this repo

Rules for contributors and coding agents are in [AGENTS.md](AGENTS.md).
