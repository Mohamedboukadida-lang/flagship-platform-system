# What broke

Problems hit and how they were fixed. Newest first.

## 2026-11-19 · M0

**The access line could not name the route template.** In the pinned FastAPI, an included router keeps its own routes, so `scope["route"].path` is `/me`, not `/v1/me`; the prefix lives on a private class. Fix: log the request path (ids, never content), truncated to 200 characters.

**The trace id was lost when a log line was formatted late.** The formatter read the current span, which is gone if a handler formats after the request (pytest's capture does; a queue handler would too). Fix: the access line stamps `request_id` and `trace_id` on the record when it is logged.

**uvicorn adds a coloured copy of each message.** Its records carry `color_message` with terminal escape codes. Fix: the formatter drops that field.

## 2026-11-16 · M0

**`ruff format` rewrote the design spec.** The pinned ruff formats Python code blocks inside Markdown, so `ruff format .` reflowed about 500 lines of `docs/system-design.md`. Fix: `extend-exclude = ["docs"]` in `pyproject.toml`; the spec holds reference sketches, not code to format.

**FastAPI's `root_path` parameter is deprecated.** The first approach to serving under `/api` used `FastAPI(root_path="/api")`; the pinned FastAPI warns that it is deprecated in favour of the server's `--root-path`, which requires the proxy to strip the prefix. Fix: an explicit setting, `LOTSE_API_PREFIX`. Routers and docs are mounted under it; `/healthz` and `/readyz` stay unprefixed for the kubelet and are also available under the prefix. No proxy rewriting is needed.

**Starlette's `TestClient` warns with httpx.** Fix: every test uses `httpx.AsyncClient` over `httpx.ASGITransport`.

**`minio/minio:latest` is not on Docker Hub.** MinIO stopped publishing images there. Nothing in M0 uses the object store, so it is not in `compose.yaml`. Decide in M1: a pinned older MinIO tag, or another S3-compatible server.

**The spec's deploy role could never be assumed.** Its trust policy matched `repo:<owner>/<repo>:ref:refs/heads/main`, but the deploy job names a GitHub environment, and then the token's subject is `repo:<owner>/<repo>:environment:demo`. Found by review, not by a failed deploy. Fix: trust the environment subject (ADR 0004).

**`terraform validate` passed code that would fail at plan time.** A `one()` over two ECR repositories only fails when values are known. Found by review. Fix: `deploy/terraform/envs/demo/tests/plan.tftest.hcl` runs the configuration against a mocked provider, in CI, without an AWS account.

**A budget with a tag filter can silently track nothing.** A cost filter on a tag only counts tags activated for cost allocation in the billing console. Fix: the budget covers the whole account.
