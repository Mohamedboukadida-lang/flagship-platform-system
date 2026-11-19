.DEFAULT_GOAL := help
.PHONY: help setup check fmt audit test test-int up down migrate seed run

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup:  ## Install dependencies; create .env from the example if missing
	uv sync --frozen
	@test -f .env || cp .env.example .env

check:  ## Lint, format check, types, import contracts, unit tests
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run lint-imports
	uv run pytest backend/tests/unit

fmt:  ## Format and apply safe lint fixes
	uv run ruff format .
	uv run ruff check --fix .

audit:  ## Check the locked runtime dependencies against known vulnerabilities
	uv export --frozen --no-dev --no-hashes --no-emit-project -q | uvx pip-audit -r /dev/stdin --disable-pip --no-deps --progress-spinner off

test-int:  ## Integration and isolation tests (need Postgres and Redis: make up)
	uv run pytest backend/tests/integration backend/tests/isolation

test: check test-int  ## Everything

up:  ## Start Postgres, Redis and Keycloak
	docker compose up -d --wait

down:  ## Stop the local stack (keeps data; add -v by hand to wipe it)
	docker compose down

migrate:  ## Apply database migrations
	uv run alembic -c backend/alembic.ini upgrade head

seed:  ## Create the two demo tenants and their members (idempotent)
	uv run python -m lotse.seed

run:  ## Run the API with reload on http://localhost:8000
	uv run uvicorn lotse.main:create_app --factory --reload --port 8000 --log-config backend/logging.json
