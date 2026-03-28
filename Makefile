.PHONY: help setup lock sync install test test-unit test-integration test-e2e test-api lint format clean config resources docker-build docker-up docker-down docker-test docker-run ci-local ci-local-stop ci-local-postgres ci-local-migrate

# Default Python / PDM (override if needed)
PYTHON ?= python3
PDM ?= pdm
DOCKER_COMPOSE ?= docker compose

# Ephemeral Postgres for `make ci-local` (same image/credentials as GitHub Actions). Override if 5432 is taken.
CI_LOCAL_PG_CONTAINER ?= verifiedsignal-ci-postgres
CI_LOCAL_PG_PORT ?= 5432
CI_LOCAL_PG_URL = postgresql://verifiedsignal:verifiedsignal@127.0.0.1:$(CI_LOCAL_PG_PORT)/verifiedsignal

help:
	@echo "VerifiedSignal — common targets"
	@echo ""
	@echo "  make setup       Install PDM (if missing) and project dependencies"
	@echo "  make lock        Refresh pdm.lock from pyproject.toml"
	@echo "  make sync        Install exactly what pdm.lock specifies"
	@echo "  make install     Alias for sync"
	@echo "  make test        Run pytest (unit + e2e; integration skips without DATABASE_URL)"
	@echo "  make test-unit   Run pytest -m unit only"
	@echo "  make test-integration  Run pytest -m integration (needs DATABASE_URL + migrations)"
	@echo "  make test-e2e    Run pytest -m e2e (needs docker on PATH)"
	@echo "  make test-api    Run pytest -m api (ASGI smoke tests)"
	@echo "  make lint        Run ruff check"
	@echo "  make format      Run ruff format"
	@echo "  make clean       Remove build and cache artifacts"
	@echo "  make config      Ensure .env from .env.example (idempotent)"
	@echo "  make resources   Placeholder for assets / downloads (extend as needed)"
	@echo "  make docker-build   Build compose images"
	@echo "  make docker-up      Run full stack: Postgres, Redis, MinIO, OpenSearch, Dashboards, app"
	@echo "  make docker-down    Stop app stack"
	@echo "  make docker-test    Run tests in Docker (compose profile: test)"
	@echo "  make docker-run     One-off app container run"
	@echo "  make ci-local       Ephemeral Postgres:16 + migrations + Ruff + pytest (mirrors CI)"
	@echo "  make ci-local-stop  Remove the ci-local Postgres container"

setup: config
	@command -v $(PDM) >/dev/null 2>&1 || { echo "Install PDM: https://pdm-project.org/latest/#installation"; exit 1; }
	$(PDM) install

lock:
	$(PDM) lock

sync:
	$(PDM) sync

install: sync

test:
	$(PDM) run python -m pytest

test-unit:
	$(PDM) run python -m pytest -m unit

test-integration:
	$(PDM) run python -m pytest -m integration

test-e2e:
	$(PDM) run python -m pytest -m e2e

test-api:
	$(PDM) run python -m pytest -m api

lint:
	$(PDM) run python -m ruff check src tests app worker

format:
	$(PDM) run python -m ruff format src tests app worker

clean:
	rm -rf .pytest_cache .ruff_cache .pdm-build dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

config:
	@test -f .env || cp .env.example .env

resources:
	@echo "No resource fetch steps defined yet. Add downloads or asset sync here."

docker-build:
	$(DOCKER_COMPOSE) build

docker-up: config
	$(DOCKER_COMPOSE) up --build

docker-down:
	$(DOCKER_COMPOSE) down

docker-test: config docker-build
	$(DOCKER_COMPOSE) --profile test run --rm test

docker-run: config docker-build
	$(DOCKER_COMPOSE) run --rm app

ci-local-stop:
	docker rm -f $(CI_LOCAL_PG_CONTAINER) 2>/dev/null || true

ci-local-postgres: ci-local-stop
	docker run -d --name $(CI_LOCAL_PG_CONTAINER) -p $(CI_LOCAL_PG_PORT):5432 \
		-e POSTGRES_USER=verifiedsignal \
		-e POSTGRES_PASSWORD=verifiedsignal \
		-e POSTGRES_DB=verifiedsignal \
		postgres:16-alpine
	until docker exec $(CI_LOCAL_PG_CONTAINER) pg_isready -U verifiedsignal -d verifiedsignal; do sleep 1; done

ci-local-migrate: ci-local-postgres
	docker exec -i $(CI_LOCAL_PG_CONTAINER) psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 \
		< db/migrations/001_initial_schema.up.sql
	docker exec -i $(CI_LOCAL_PG_CONTAINER) psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 \
		< db/migrations/002_intake_document_fields.up.sql

ci-local: ci-local-migrate
	env DATABASE_URL='$(CI_LOCAL_PG_URL)' $(PDM) run python -m ruff check src tests app worker
	env DATABASE_URL='$(CI_LOCAL_PG_URL)' $(PDM) run python -m pytest -v --tb=short
