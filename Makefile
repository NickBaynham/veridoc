.PHONY: help setup lock sync install test test-unit test-integration test-e2e test-api lint format clean config resources docker-build docker-up docker-down docker-test docker-run

# Default Python / PDM (override if needed)
PYTHON ?= python3
PDM ?= pdm
DOCKER_COMPOSE ?= docker compose

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
