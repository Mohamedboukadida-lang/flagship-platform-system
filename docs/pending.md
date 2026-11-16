# Pending

What is not done yet, in order. When an item lands on `main`, move it to `docs/progress.md`.

## To close M0

Exit gate: a logged-in request returns the caller's tenant on the public URL; the isolation suite runs in CI.

1. Review and merge the branch `m0-walking-skeleton`.
2. First deployment, by the owner, following `docs/runbooks/demo-deploy.md`: state bucket, `terraform apply`, fill the secret, GitHub variables and the `demo` environment.
3. Run `deploy/smoke.sh` against the public URL with `SMOKE_PASSWORD` set. That is the gate.
4. Commit the `.terraform.lock.hcl` files created by the first `terraform init`.

Expect step 2 to need fixes. These parts have never run: the node's first-boot script (k3s, Helm and cert-manager on Ubuntu 24.04), the release document, `deploy.yml`, the chart on a real cluster (hooks, probes, ingress, certificate).

## Known gaps in M0, on purpose

| Gap | Why | When |
| --- | --- | --- |
| No object store locally or in AWS | Nothing uses it yet; MinIO no longer publishes its image on Docker Hub | M1 |
| No backups | The demo holds seed data only | M1, with the scheduler |
| Pods cannot use AWS credentials (metadata hop limit 1) | Nothing in a pod calls AWS yet | M1, for S3 |
| Secret synced by the release script, not External Secrets Operator | One operator less on a small node | M8 or earlier |
| `lotse-cli` client allows the password grant | Needed for smoke tests and `curl` | Remove before real users |
| No rate limiting, idempotency keys or audit log | Not part of the M0 slice list | M1 and M2 |
| CI has no gitleaks, dependency audit or image scan | Kept the first pipeline small | M8, or sooner |
| GitHub Actions pinned by tag, not by commit SHA | The SHAs could not be looked up from the build sandbox | Next CI change |
| k3s channel and cert-manager chart not pinned to exact versions | Unknown until the first apply | After the first apply |
| No HTTP to HTTPS redirect, no network policies | Hardening | M8 |
| No worker process | No jobs yet | M1 |

## M1: documents and ingestion (30 Nov to 13 Dec)

Spec section 8. Write the slice list here before starting. Exit gate: a 50-page PDF becomes searchable; killing the worker mid-ingest loses nothing.

Cut order if time runs short: MCP server, router, semantic cache, memory, forensics diff.

## Repo housekeeping (optional, small)

- Branch protection on `main` with `ci` required
- Pull request template
- Secret scanning and Dependabot in the repository settings
