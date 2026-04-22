# Commands reference

Run `make` or `make help` for the live list from the [Makefile](../Makefile).

## Makefile — common

| Command | Purpose |
|--------|---------|
| `make setup` | `make config` + `pdm install` |
| `make config` | `.env` from `.env.example` if missing |
| `make lock` / `make sync` | Refresh or install from `pdm.lock` |
| `make test` | Pytest (integration skips if `DATABASE_URL` unset) |
| `make test-unit` | `pytest -m unit` |
| `make test-integration` | `pytest -m integration` |
| `make test-e2e` | `pytest -m e2e` |
| `make test-api` | `pytest -m api` |
| `make ci-local` | Ephemeral Postgres + migrations + Ruff + pytest + coverage |
| `make ci-local-stop` | Remove ci-local Postgres container |
| `make lint` / `make format` | Ruff |
| `make clean` | Drop caches |
| `make web-config` | `apps/web/.env.local` from example if missing |
| `make web-dev` | Vite dev server in `apps/web` |
| `make dev-stack` | Compose: Postgres, Redis, MinIO, OpenSearch, Dashboards |
| `make dev` / `make local` | `dev-stack` + host API (`api-local`) |
| `make dev-down` | Stop dev-stack services |
| `make api-local` | Compose Postgres + host FastAPI |
| `make api-local-restart` | Free API port and restart `api-local` |
| `make install-supabase` | Supabase CLI hints (Homebrew) |
| `make docker-build` / `docker-up` / `docker-down` / `docker-test` / `docker-run` | See [docker-compose.md](docker-compose.md) |

## PDM (without Make)

```bash
pdm install
pdm lock
pdm add <package>
pdm add -dG dev <pkg>
pdm run python -m pytest
pdm run python -m pytest -m "not integration"   # matches default CI subset
pdm run python -m pytest --cov=app/services --cov-report=term-missing
pdm run api / api-prod / worker
pdm run python -m ruff check src tests app worker scripts mcp_server
```

Runtime deps: `[project]` in `pyproject.toml`. Dev tools: `[dependency-groups] dev`.

## Docker / Compose (quick)

| Command | Purpose |
|--------|---------|
| `make docker-build` | Build app image |
| `make docker-up` | Full stack foreground |
| `make docker-down` | Stop services, keep volumes |
| `make docker-test` | Pytest in `test` service |
| `docker compose up -d postgres redis minio opensearch ...` | Infra only |
| `docker compose --profile test run --rm test` | Pytest without Make |

More detail: [docker-compose.md](docker-compose.md).

Make variables `PDM` and `DOCKER_COMPOSE` default to `pdm` and `docker compose`.
