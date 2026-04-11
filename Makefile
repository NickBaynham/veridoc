.PHONY: help setup lock sync install install-supabase test test-unit test-integration test-e2e test-api lint format clean config resources docker-build docker-up docker-down docker-test docker-run web-config web-dev api-local api-local-prod api-local-restart migrate migrate-002 migrate-003 migrate-reset ci-local ci-local-stop ci-local-postgres ci-local-migrate-sql ci-local-migrate

# Default Python / PDM (override if needed)
PYTHON ?= python3
PDM ?= pdm
DOCKER_COMPOSE ?= docker compose

# Ephemeral Postgres for `make ci-local` (same image/credentials as GitHub Actions).
# Default host port 5433 avoids clashing with Compose Postgres on 5432; override with CI_LOCAL_PG_PORT=5432 if free.
CI_LOCAL_PG_CONTAINER ?= verifiedsignal-ci-postgres
CI_LOCAL_PG_PORT ?= 5433
CI_LOCAL_PG_URL = postgresql://verifiedsignal:verifiedsignal@127.0.0.1:$(CI_LOCAL_PG_PORT)/verifiedsignal

# Host-side service URLs for `make api-local` / `api-local-prod` (pdm run api on your machine while
# Postgres / Redis / MinIO / OpenSearch run in Docker with default published ports).
# Override any piece, e.g. `make api-local LOCAL_API_PG_PORT=5433` or set LOCAL_API_DATABASE_URL entirely.
LOCAL_API_DB_USER ?= verifiedsignal
LOCAL_API_DB_PASSWORD ?= verifiedsignal
LOCAL_API_DB_NAME ?= verifiedsignal
LOCAL_API_PG_PORT ?= 5432
LOCAL_API_REDIS_PORT ?= 6379
LOCAL_API_MINIO_PORT ?= 9000
LOCAL_API_OS_PORT ?= 9200
LOCAL_API_DATABASE_URL ?= postgresql://$(LOCAL_API_DB_USER):$(LOCAL_API_DB_PASSWORD)@127.0.0.1:$(LOCAL_API_PG_PORT)/$(LOCAL_API_DB_NAME)
# HTTP bind for api-local / api-local-prod (override if 8000 is in use, e.g. another uvicorn).
LOCAL_API_PORT ?= 8000

# `make migrate` — Docker Compose postgres service (must be running: docker compose up -d postgres).
COMPOSE_POSTGRES_SERVICE ?= postgres
COMPOSE_DB_USER ?= verifiedsignal
COMPOSE_DB_NAME ?= verifiedsignal

# env(1) prefix applied before `pdm run api` for local host development
API_LOCAL_ENV = env \
	DATABASE_URL='$(LOCAL_API_DATABASE_URL)' \
	REDIS_URL='redis://127.0.0.1:$(LOCAL_API_REDIS_PORT)/0' \
	S3_ENDPOINT_URL='http://127.0.0.1:$(LOCAL_API_MINIO_PORT)' \
	OPENSEARCH_URL='http://127.0.0.1:$(LOCAL_API_OS_PORT)'

help:
	@echo "VerifiedSignal — common targets"
	@echo ""
	@echo "  make setup       Install PDM (if missing) and project dependencies"
	@echo "  make install-supabase  Install Supabase CLI (Homebrew when available; see supabase/README.md)"
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
	@echo "  make web-config     Create apps/web/.env.local from .env.example if missing (API → Docker :8000)"
	@echo "  make web-dev        web-config + npm run dev in apps/web (npm install in apps/web once first)"
	@echo "  make migrate        Apply 001–005 (fails if 001 already applied — use migrate-00x or migrate-reset)"
	@echo "  make migrate-002    Apply only 002 (when 001 is already on the database)"
	@echo "  make migrate-003    Apply only 003 (body_text column; when 001+002 already applied)"
	@echo "  make migrate-004    Apply only 004 (extract_artifact_key; when 001–003 already applied)"
	@echo "  make migrate-005    Apply only 005 (user_metadata; when 001–004 already applied)"
	@echo "  make migrate-reset  Drop app schema + re-apply 001–005 (dev only; needs MIGRATE_RESET_OK=1)"
	@echo "  make api-local      Run FastAPI on host with 127.0.0.1 URLs (LOCAL_API_PG_PORT, LOCAL_API_PORT=8000)"
	@echo "  make api-local-prod Same as api-local without --reload"
	@echo "  make api-local-restart  Kill process on LOCAL_API_PORT then run api-local (same vars)"
	@echo "  make ci-local       Ephemeral Postgres:16 + migrations 001–005 + Ruff + pytest --cov=app/services; removes container after (even on failure)"
	@echo "  make ci-local-stop  Remove the ci-local Postgres container (manual cleanup)"

setup: config
	@command -v $(PDM) >/dev/null 2>&1 || { echo "Install PDM: https://pdm-project.org/latest/#installation"; exit 1; }
	$(PDM) install

# Supabase CLI: local auth stack for /auth/* (Docker must be running for `supabase start`).
install-supabase:
	@set -e; \
	if command -v supabase >/dev/null 2>&1; then \
		echo "Supabase CLI already installed:"; \
		supabase --version; \
	elif command -v brew >/dev/null 2>&1; then \
		echo "Installing Supabase CLI via Homebrew..."; \
		brew install supabase/tap/supabase || brew install supabase; \
		supabase --version; \
	else \
		echo >&2 "Homebrew not found. Install the Supabase CLI manually:"; \
		echo >&2 "  https://supabase.com/docs/guides/cli/getting-started"; \
		echo >&2 "Windows (Scoop): scoop bucket add supabase https://github.com/supabase/scoop-bucket.git && scoop install supabase"; \
		echo >&2 "Node 20+: npx supabase --version"; \
		exit 1; \
	fi

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
	$(PDM) run python -m ruff check src tests app worker scripts

format:
	$(PDM) run python -m ruff format src tests app worker scripts

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

web-config:
	@test -f apps/web/.env.local || { echo "Creating apps/web/.env.local from apps/web/.env.example"; cp apps/web/.env.example apps/web/.env.local; }

web-dev: web-config
	cd apps/web && npm run dev

migrate:
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/001_initial_schema.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/002_intake_document_fields.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/003_document_body_text.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/004_document_extract_artifact.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/005_documents_user_metadata.up.sql

migrate-002:
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/002_intake_document_fields.up.sql

migrate-003:
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/003_document_body_text.up.sql

migrate-004:
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/004_document_extract_artifact.up.sql

migrate-005:
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/005_documents_user_metadata.up.sql

migrate-reset:
ifeq ($(MIGRATE_RESET_OK),1)
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/005_documents_user_metadata.down.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/004_document_extract_artifact.down.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/003_document_body_text.down.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/002_intake_document_fields.down.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/001_initial_schema.down.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/001_initial_schema.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/002_intake_document_fields.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/003_document_body_text.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/004_document_extract_artifact.up.sql
	$(DOCKER_COMPOSE) exec -T $(COMPOSE_POSTGRES_SERVICE) psql -U $(COMPOSE_DB_USER) -d $(COMPOSE_DB_NAME) -v ON_ERROR_STOP=1 < db/migrations/005_documents_user_metadata.up.sql
else
	@echo >&2 "migrate-reset drops all VerifiedSignal tables and data (005 down … 001 down, then 001…005 up)."
	@echo >&2 "To confirm: make migrate-reset MIGRATE_RESET_OK=1"
	@exit 1
endif

api-local:
	$(API_LOCAL_ENV) $(PDM) run python -m uvicorn app.main:app --host 0.0.0.0 --port $(LOCAL_API_PORT) --reload

api-local-prod:
	$(API_LOCAL_ENV) $(PDM) run python -m uvicorn app.main:app --host 0.0.0.0 --port $(LOCAL_API_PORT)

# Free LOCAL_API_PORT (SIGTERM then SIGKILL) so a new uvicorn can bind; then start api-local.
api-local-restart:
	@echo "Stopping listeners on TCP port $(LOCAL_API_PORT) (if any)…"
	@for p in $$(lsof -nP -tiTCP:$(LOCAL_API_PORT) -sTCP:LISTEN 2>/dev/null | sort -u); do \
		[ -n "$$p" ] && kill "$$p" 2>/dev/null || true; \
	done; \
	sleep 1; \
	for p in $$(lsof -nP -tiTCP:$(LOCAL_API_PORT) -sTCP:LISTEN 2>/dev/null | sort -u); do \
		[ -n "$$p" ] && kill -9 "$$p" 2>/dev/null || true; \
	done
	$(MAKE) api-local

ci-local-stop:
	docker rm -f $(CI_LOCAL_PG_CONTAINER) 2>/dev/null || true

ci-local-postgres: ci-local-stop
	docker run -d --name $(CI_LOCAL_PG_CONTAINER) -p $(CI_LOCAL_PG_PORT):5432 \
		-e POSTGRES_USER=verifiedsignal \
		-e POSTGRES_PASSWORD=verifiedsignal \
		-e POSTGRES_DB=verifiedsignal \
		postgres:16-alpine
	until docker exec $(CI_LOCAL_PG_CONTAINER) pg_isready -U verifiedsignal -d verifiedsignal; do sleep 1; done

# Apply migrations to an already-running $(CI_LOCAL_PG_CONTAINER) (used by ci-local without restarting Postgres).
ci-local-migrate-sql:
	docker exec -i $(CI_LOCAL_PG_CONTAINER) psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 \
		< db/migrations/001_initial_schema.up.sql
	docker exec -i $(CI_LOCAL_PG_CONTAINER) psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 \
		< db/migrations/002_intake_document_fields.up.sql
	docker exec -i $(CI_LOCAL_PG_CONTAINER) psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 \
		< db/migrations/003_document_body_text.up.sql
	docker exec -i $(CI_LOCAL_PG_CONTAINER) psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 \
		< db/migrations/004_document_extract_artifact.up.sql
	docker exec -i $(CI_LOCAL_PG_CONTAINER) psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 \
		< db/migrations/005_documents_user_metadata.up.sql

ci-local-migrate: ci-local-postgres ci-local-migrate-sql

# One shell: EXIT trap runs for any failure (including docker bind errors) so the named container is not left behind.
ci-local:
	set -e; \
	trap 'docker rm -f $(CI_LOCAL_PG_CONTAINER) 2>/dev/null || true' EXIT; \
	$(MAKE) ci-local-postgres; \
	$(MAKE) ci-local-migrate-sql; \
	env DATABASE_URL='$(CI_LOCAL_PG_URL)' $(PDM) run python -m ruff check src tests app worker scripts; \
	env DATABASE_URL='$(CI_LOCAL_PG_URL)' $(PDM) run python -m pytest -v --tb=short \
		--cov=app/services --cov-report=term-missing --cov-report=xml
