# Pending

What is not done yet, in order. When an item lands on `main`, move it to `docs/progress.md`.

## To close M0

Exit gate: a logged-in request returns the caller's tenant on the public URL; the isolation suite runs in CI.

1. First deployment, by the owner, following `docs/runbooks/demo-deploy.md`: state bucket, `terraform apply`, fill the secret, GitHub variables and the `demo` environment.
2. Run `deploy/smoke.sh` against the public URL with `SMOKE_PASSWORD` set. That is the gate.
3. Commit the `.terraform.lock.hcl` files created by the first `terraform init`.

Expect step 2 to need fixes. These parts have never run: the node's first-boot script (k3s, Helm and cert-manager on Ubuntu 24.04), the release document, `deploy.yml`, the chart on a real cluster (hooks, probes, ingress, certificate).

## Known gaps in M0, on purpose

| Gap | Why | When |
| --- | --- | --- |
| No files bucket in AWS yet (local RustFS only) | Nothing uploads yet | M1 slice 10 |
| No backups | The demo holds seed data only | M1, with the scheduler |
| Pods cannot use AWS credentials (metadata hop limit 1) | Nothing in a pod calls AWS yet | M1, for S3 |
| Secret synced by the release script, not External Secrets Operator | One operator less on a small node | M8 or earlier |
| `lotse-cli` client allows the password grant | Needed for smoke tests and `curl` | Remove before real users |
| No rate limiting, idempotency keys or audit log | Not part of the M0 slice list | M1 and M2 |
| CI has no image scan | Secret scan and dependency audit landed 2026-11-18; ECR scans images on push | M8 |
| GitHub Actions pinned by tag, not by commit SHA | The SHAs could not be looked up from the build sandbox; Dependabot now keeps the tags current | When Dependabot's first actions update lands |
| k3s channel and cert-manager chart not pinned to exact versions | Unknown until the first apply | After the first apply |
| No HTTP to HTTPS redirect, no network policies | Hardening | M8 |
| No worker process | No jobs yet | M1 |

## M1: documents and ingestion (30 Nov to 13 Dec)

Spec section 8. Exit gate: a 50-page PDF becomes searchable; killing the worker mid-ingest loses nothing.

Draft slice list. Confirm or reorder before starting; each slice ends with its check passing in CI.

| # | Slice | Acceptance check |
| --- | --- | --- |
| ~~1~~ | ~~Object store~~ | Done 2026-11-25 (RustFS locally; see `docs/progress.md`) |
| 2 | Schema: `collections`, `collection_grants`, `documents`, `document_versions`, `chunks` (with `vector(768)` and the generated `tsv`), each with forced RLS | The isolation suite picks the new tables up and passes; two-tenant read and write tests per table |
| 3 | Job queue: `jobs` table, `core/jobs.py` with `enqueue` inside the caller's transaction, claim with `SKIP LOCKED`, lease, backoff, `dead` after the last attempt | Unit tests for backoff; integration: two workers never claim the same job; an expired lease is claimed again; a rolled-back request leaves no job |
| 4 | Worker process `lotse.worker`: semaphore, per-kind timeout, graceful stop on SIGTERM, tenant session from the job row | Integration: SIGTERM lets the running job finish; a handler error requeues with backoff; the worker sees only the job's tenant |
| 5 | Collections and upload API: `POST/GET /v1/collections`, `POST /v1/collections/{id}/documents` returns a presigned PUT, `POST /v1/documents/{id}/complete` checks size and SHA-256 and enqueues `ingest_document` | Integration: happy path; changed file gets 409; same hash is a no-op; another tenant's id is 404; `documents:write` required |
| 6 | Parse and chunk: PDF, Markdown, plain text into sections; `chunk.py` per the spec (token target 400, overlap 60, never across headings) | Unit tests with small fixtures, including an oversized paragraph and a heading-only section; type sniffing rejects a renamed file |
| 7 | Embeddings: a minimal `llm/client.py` with `embed()` against an OpenAI-compatible endpoint (Ollama locally), plus a fake for tests; import-linter contract that only `llm/` calls model endpoints | Unit tests with the fake; one integration test against Ollama marked optional |
| 8 | Ingest handler: download, parse, chunk, skip known `content_hash`, embed in batches, one transaction to swap versions and set `ready` | Integration: a document becomes `ready` with chunks; killing the worker mid-ingest and restarting finishes without duplicates (the exit gate) |
| 9 | Search check: a plain hybrid query (vector and full text) over `chunks` to prove "searchable"; the real retrieval module is M2 | A question about a fixture PDF returns its chunk first; a 50-page PDF is searchable within 60 s locally |
| 10 | Deploy pieces: worker Deployment in the chart, S3 bucket and pod access in Terraform, ADR 0005 (job table instead of a broker) | `helm lint`, `terraform validate` and `test`; ADR written |

Decision needed before slice 2:

- **Embedding model and dimension.** The schema fixes the vector size, and changing it later means re-embedding everything. Recommendation: `nomic-embed-text` in Ollama (768 dimensions, the spec's default, runs on CPU), unless the hosted EU endpoint you plan to use offers a different model.

Notes for later slices:

- Slice 5: `complete` can use `ObjectStore.head` to compare the stored size and SHA-256 with the registered ones; no download in the API.
- Slice 10: create the files bucket with the name Terraform already computes (`<name>-files-<account>`), give the API and worker pods access to it, and add the object store to `/readyz`.

Cut order if time runs short: MCP server, router, semantic cache, memory, forensics diff.

## Repo housekeeping (repository settings, owner only)

- Branch protection on `main` with the `ci` jobs required
- Secret scanning and push protection in Settings, Code security
