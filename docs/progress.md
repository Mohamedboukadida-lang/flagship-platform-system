# Progress

What has landed on `main`. Newest entry first. One entry per working session: what landed, how it was verified, what is next.

## Milestones

| Milestone | Dates | Status | Exit gate |
| --- | --- | --- | --- |
| M0 Walking skeleton | 16 Nov to 29 Nov 2026 | In progress (repo prepared) | A logged-in request returns the caller's tenant on the public URL; isolation suite runs in CI |
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

### 2026-11-16 · M0 · repository prepared

- Landed: `AGENTS.md` (agent and project rules), `CLAUDE.md` (pointer to it), `README.md`, `.gitignore`, `.editorconfig`, `docs/progress.md`, `docs/pending.md`.
- Verified: files only, nothing to run. Checked that no secrets, account IDs or personal data are in the commit.
- Not done: no code, no CI, no infrastructure, design spec not committed.
- Next: owner decisions in `docs/pending.md`, then M0 slice 1.
