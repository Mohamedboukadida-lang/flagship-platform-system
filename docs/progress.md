# Progress

What has landed on `main`. Newest entry first. One entry per working session: what landed, how it was verified, what is next.

## Milestones

| Milestone | Dates | Status | Exit gate |
| --- | --- | --- | --- |
| M0 Walking skeleton | 16 Nov to 29 Nov 2026 | Code complete, verified locally; not deployed | A logged-in request returns the caller's tenant on the public URL; isolation suite runs in CI |
| M1 Documents and ingestion | 30 Nov to 13 Dec | Not started | A 50-page PDF becomes searchable; killing the worker mid-ingest loses nothing |
| M2 Gateway, RAG and chat | 14 Dec to 20 Dec, 4 Jan to 17 Jan 2027 | Not started | Golden set baseline and ablation table for four retrieval modes |
| M3 Console v1 | 18 Jan to 31 Jan | Not started | End-to-end test: log in, upload, ask, click a citation |
| M4 Quality gate and forensics | 1 Feb to 14 Feb | Not started | A worse prompt in a pull request is blocked; a failed trace becomes a test case |
| M5 Text-to-SQL | 22 Feb to 7 Mar | Not started | Adversarial suite: zero writes, zero out-of-scope reads |
| M6 Agents and approvals | 8 Mar to 28 Mar | Not started | Approval survives a worker restart; each side effect happens once in 10 of 10 trials |
| M7 Cost and admin | 29 Mar to 11 Apr | Not started | Cost versus quality table against always-strong; a tenant cannot exceed its budget |
| M8 Hardening and launch | 12 Apr to 18 Apr | Not started | Quality targets from spec section 1 measured and published |

Buffers (catch-up only): 21 Dec to 3 Jan, 15 Feb to 21 Feb.

## Log

### 2026-11-18 · M0 · repository hygiene and M1 plan

- Landed: a `security` CI job (gitleaks on the pushed commits, `make audit` with pip-audit on the locked runtime dependencies), Dependabot for uv, GitHub Actions, the Docker base image and Terraform, a pull request template, and the M1 slice list in `docs/pending.md`.
- Verified: gitleaks over the full history found nothing (11 commits); `make audit` found no known vulnerabilities; actionlint passes on both workflows.
- Not done: branch protection and secret scanning are repository settings only the owner can change.

### 2026-11-16 · M0 · walking skeleton, all nine slices

Landed on the branch `m0-walking-skeleton`:

| Slice | What | Evidence from this session |
| --- | --- | --- |
| 1 Tooling | `pyproject.toml`, `uv.lock`, `Makefile` | `make check`: ruff, mypy strict, 3 import contracts, 32 unit tests |
| 2 Local stack | `compose.yaml`: Postgres, Redis, Keycloak | All three healthy; Keycloak issued a token with the right audience and user id |
| 3 CI | `ci.yml`: checks, tests, image build, Terraform and Helm checks | See the Actions tab for the branch |
| 4 Core | Settings, problem+json errors, UUIDv7, tracing, request id, health | Unit tests; `/readyz` returns 503 naming the failed store |
| 5 Schema | Roles, `tenants`, `users`, `memberships`, forced RLS | 26 isolation tests as the runtime roles; 4 of them prove the gate fails on an unprotected table |
| 6 Auth | RS256 validation, `Principal`, `GET /v1/me` | 14 integration tests; end to end with a real Keycloak login |
| 7 Image and chart | `api.Dockerfile`, `deploy/helm/lotse` | Image built and run as uid 10001; `helm lint`; every container run with the chart's settings in Docker, login succeeded |
| 8 Terraform and deploy | `deploy/terraform`, `deploy.yml`, release and smoke scripts | `fmt`, `validate`, 3 mocked plan tests, checkov 120 passed and 0 failed; smoke script tested locally. **Never applied to AWS** |
| 9 ADRs | `docs/decisions/0001` to `0004` | Written |

Not verified: anything that needs an AWS account or a Kubernetes cluster. The chart was never installed on a cluster (kind could not start in the build sandbox), and the node bootstrap, the release document and `deploy.yml` have never run. The M0 exit gate (login on the public URL) is therefore still open; the steps are in `docs/runbooks/demo-deploy.md`.

Problems hit are in `docs/what-broke.md`.

### 2026-11-16 · M0 · spec and owner decisions

- Landed: `docs/system-design.md` (the spec, personal planning notes removed), `LICENSE`.
- Decided by the owner: the name stays Lotse; MIT license; a new state bucket for this project; the demo stays deployed with a budget alarm and the instance stopped outside demo hours.
- Verified: the spec copy differs from the original only in the byline, two wording changes, the hours column and two removed lines.

### 2026-11-16 · M0 · repository prepared

- Landed: `AGENTS.md` (agent and project rules), `CLAUDE.md` (pointer to it), `README.md`, `.gitignore`, `.editorconfig`, `docs/progress.md`, `docs/pending.md`.
- Verified: files only, nothing to run. Checked that no secrets, account IDs or personal data are in the commit.
- Not done: no code, no CI, no infrastructure, design spec not committed.
- Next: owner decisions in `docs/pending.md`, then M0 slice 1.
