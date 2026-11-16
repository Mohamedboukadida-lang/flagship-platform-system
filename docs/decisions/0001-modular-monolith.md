# 0001: Modular monolith with two processes

Status: accepted, 2026-11-16 (M0)

## Decision

One codebase and one image, started as two processes: the API (`lotse.main`) and, from M1, the worker (`lotse.worker`). Features live in `lotse/modules/<name>/` with a fixed shape: `service.py` holds logic and takes a database handle and a `Principal`; `api.py` is a thin router. Modules call each other through `service.py` functions only.

## Why

One developer. Module boundaries give the structure of services without network hops, separate deployments or distributed transactions.

## Alternatives

- Microservices per feature: operational cost with no team to benefit from it.
- An unstructured monolith: cheap now, expensive to split later.

## How it is enforced

`import-linter` contracts in `pyproject.toml`, run by `make check`:

- `lotse.core` does not import feature modules.
- `service.py` files do not import FastAPI or Starlette.
- Only `lotse.core.db` imports the database driver.

## Consequences

A later split into services stays possible because no module reads another module's tables. The API must never do slow work in a request; that goes to the worker through the job table (ADR 0005, M1).
