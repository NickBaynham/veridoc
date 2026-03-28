# VerifiedSignal

A document intelligence platform. This repository uses **Python** with **[PDM](https://pdm-project.org/latest/)** for dependencies, a **Makefile** for setup and common tasks, and **Docker Compose** for local infrastructure. **PostgreSQL** is the system-of-record; **OpenSearch** is a derived, disposable index; a **FastAPI** service exposes synchronous HTTP + **SSE**; an **ARQ** worker runs async background jobs on **Redis**.

## What’s included so far

This repo is an **early scaffold** with the following in place:

- **CLI package** — Python **3.11+**, `src/verifiedsignal/`, small CLI (`pdm run python -m verifiedsignal`, `pdm run verifiedsignal`).
- **HTTP API** — root package **`app/`**: **FastAPI** (`app/main.py`), **`/api/v1`** routes for **health** (Postgres, Redis, object storage, OpenSearch reachability), info, **Phase 1 document intake** (`POST /api/v1/documents` multipart upload → Postgres + MinIO/S3 + ARQ), search stub, and **SSE** (`/api/v1/events/stream`). **SQLAlchemy** session factory for Postgres (`app/db/session.py`); placeholder auth (`app/auth/placeholder.py`).
- **Worker** — root package **`worker/`**: **[ARQ](https://arq-docs.helpmanual.io/)** worker on Redis (`pdm run worker`), `process_document` task with **simulated pipeline stages** (`worker/pipeline.py`). Intended to evolve into real ingestion, scoring, and OpenSearch indexing (all driven from Postgres truth).
- **PDM** — `pyproject.toml`, **`pdm.lock`**, scripts: **`pdm run api`** (uvicorn reload), **`pdm run api-prod`**, **`pdm run worker`**, dev group (**pytest**, **ruff**, etc.).
- **Makefile** — `setup`, `lock` / `sync`, `test` / `test-unit` / `test-integration` / `test-e2e` / **`test-api`**, **`ci-local`** / **`ci-local-stop`**, `lint`, `format`, Docker targets.
- **Tests** — **`pytest`** markers: **`unit`**, **`integration`**, **`e2e`**, **`api`**. See **[`tests/README.md`](tests/README.md)**.
- **CI** — **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)** — Ruff on `src`, `tests`, `app`, `worker`; Postgres **16** + migrations; **`pdm run python -m pytest`** (full suite).
- **Docker** — **`Dockerfile`** copies `app/`, `worker/`, `src/`, `tests/`, `db/`, sets **`PYTHONPATH=/app`**, default CMD **`api-prod`** (uvicorn).
- **Docker Compose** — infra + runtimes:
  - **PostgreSQL**, **Redis**, **MinIO**, **OpenSearch**, **Dashboards**
  - **`app`** — FastAPI on **`8000`** (depends on **postgres** + **redis**)
  - **`worker`** — ARQ consumer (depends on **redis**)
  - **`test`** — pytest (**profile:** `test`)
- **Configuration** — **`.env.example`** (ports, DB/Redis/S3/OpenSearch URLs), **`config/application.example.yml`**, **`config/`** mounted read-only into the app container.
- **Canonical database schema** — SQL migrations under **`db/migrations/`** (users, organizations, collections, documents, sources, pipeline runs/events, document scores). See **[`db/README.md`](db/README.md)** for how to apply them and architectural notes (Postgres as source of truth, OpenSearch as disposable index).

## Prerequisites

- **Python** 3.11 or newer
- **[PDM](https://pdm-project.org/latest/#installation)** on your `PATH` (`pdm --version`)
- **GNU Make**
- **Docker** and **Docker Compose** v2 (`docker compose version`) if you use the container workflow

## Quick start (local)

1. Clone the repository and enter the project directory.

2. Install dependencies and create a local `.env` from the example (if `.env` does not exist):

   ```bash
   make setup
   ```

   If PDM is not installed, follow the [official PDM installation guide](https://pdm-project.org/latest/#installation) and run `make setup` again.

3. Run the CLI:

   ```bash
   pdm run python -m verifiedsignal
   ```

   Or use the console script:

   ```bash
   pdm run verifiedsignal
   ```

4. Run tests and linters:

   ```bash
   make test
   make lint
   ```

   For a **full suite on your machine** (including integration tests against real Postgres), see **[Testing locally](#testing-locally)** below.

## Testing locally

### Quick run (no Postgres)

After **`make setup`**:

```bash
make test    # unit, e2e, api; integration skips if DATABASE_URL is unset
make lint
```

Integration tests that need a database are skipped unless **`DATABASE_URL`** is set and migrations **001** and **002** are applied. Markers and behavior are described in **[`tests/README.md`](tests/README.md)**.

### Full suite like CI (ephemeral Postgres in Docker)

**[`Makefile`](Makefile)** includes targets that mirror **GitHub Actions**: **Postgres 16**, same user/password/database as CI, migrations **001** + **002**, then **Ruff** and **pytest** with the correct **`DATABASE_URL`**.

```bash
make setup          # once: dependencies + .env from example if missing
make ci-local       # ephemeral Postgres + migrations + lint + pytest; **removes the container when done** (including on failure)
make ci-local-stop  # optional: remove the container if you started Postgres without a full ci-local run
```

- Requires **Docker** on your `PATH`. By default the DB is published on host port **`5433`** so **`make ci-local`** does not fight **Compose Postgres** on **5432**. To use **5432** instead (when it is free):

  ```bash
  make ci-local CI_LOCAL_PG_PORT=5432
  ```

- **`make ci-local`** removes any existing container named **`verifiedsignal-ci-postgres`** (see **`CI_LOCAL_PG_CONTAINER`** in the Makefile) before starting, and **removes it again on exit** (success or failure) so the next run is not blocked on the port.

- **`DATABASE_URL` in the process environment** (as set by **`make ci-local`**) takes precedence over **`.env`** for the running app, so SQLAlchemy and **`psycopg`** in tests use the same DSN. If you previously saw “password authentication failed” only on **`POST /documents`** while other integration tests passed, a mismatched **`.env`** was the usual cause.

### Compose Postgres (reuse your dev database)

If you prefer the project’s **Compose** Postgres:

```bash
docker compose up -d postgres
```

Apply **001** then **002** from the repo root (examples in **[`db/README.md`](db/README.md)**), then point **`DATABASE_URL`** at the instance (typically **`postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal`** from the host) and run:

```bash
make test
# or only integration-marked tests:
make test-integration
```

### Tests inside Docker

**`make docker-test`** builds the app image and runs **pytest** in the Compose **`test`** service (see **[Useful commands](#useful-commands)**).

## HTTP API and worker (local)

**Why separate runtimes?** The API process optimizes for **low-latency request/response**, **SSE**, and **auth** at the edge. Workers optimize for **long-running**, **CPU/IO-heavy** steps (extract, score, bulk index) without blocking clients. Redis/ARQ decouples them so you can scale API and worker tiers independently and restart workers without dropping HTTP availability.

**Phase 1 intake (implemented):** `POST /api/v1/documents` accepts **multipart/form-data** with a file. The API validates input, inserts a canonical **`documents`** row in **`created`**, uploads bytes to **S3-compatible storage** (MinIO locally) under `raw/{document_id}/{safe_filename}`, updates the row to **`queued`**, inserts **`document_sources`** with an `s3://{bucket}/{key}` locator, then enqueues **`process_document`** on ARQ. If enqueue fails, the row stays **`queued`** with **`enqueue_error`** set; the object and Postgres metadata are kept.

**Still stubbed / later stages:** extraction, LLM scoring, OpenSearch indexing, full **`pipeline_runs`** wiring, and durable cross-instance SSE (today’s **`EventHub`** is in-process).

### Run the API (uvicorn)

From the repo root (PDM puts the project on `PYTHONPATH`):

```bash
make setup
export DATABASE_URL=postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal
# Apply migrations 001 + 002 (intake columns + default collection seed) — see db/README.md
export REDIS_URL=redis://localhost:6379/0
# MinIO / S3 (omit and set USE_FAKE_STORAGE=true to store bytes in-memory only)
export S3_ENDPOINT_URL=http://127.0.0.1:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export S3_BUCKET=verifiedsignal
export S3_USE_PATH_STYLE=true
# Optional: no Redis — in-memory queue (worker will not see jobs)
export USE_FAKE_QUEUE=true
# Optional: no MinIO — keep objects in-process only (good for quick API tries)
# export USE_FAKE_STORAGE=true

pdm run api
# → http://127.0.0.1:8000/api/v1/health
```

Production-style (no reload):

```bash
pdm run api-prod
```

### Run the worker (ARQ)

Requires **Redis** and **`USE_FAKE_QUEUE` unset/false** for the API when you want real enqueue:

```bash
export REDIS_URL=redis://localhost:6379/0
pdm run worker
```

### MinIO locally (object storage)

Start MinIO (Docker example):

```bash
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  quay.io/minio/minio server /data --console-address ":9001"
```

Create the **`verifiedsignal`** bucket once (Console at [http://127.0.0.1:9001](http://127.0.0.1:9001), or **`mc`**). The **`S3ObjectStorage`** adapter attempts **`create_bucket`** if **`head_bucket`** reports a missing bucket (simple dev convenience; production often provisions buckets out-of-band).

Point the API at MinIO with **`S3_ENDPOINT_URL`** (e.g. `http://127.0.0.1:9000`) and **`S3_USE_PATH_STYLE=true`**.

### Minimal API checks

```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq
curl -s -X POST http://127.0.0.1:8000/api/v1/documents \
  -F "file=@./README.md;type=text/markdown" \
  -F "title=Demo upload" | jq
# Optional explicit collection (otherwise VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID / seeded default-inbox)
# -F "collection_id=00000000-0000-4000-8000-000000000002"
```

SSE (example — streams until you Ctrl+C):

```bash
curl -N http://127.0.0.1:8000/api/v1/events/stream
```

## Useful commands

### Local development

| Command | Purpose |
|--------|---------|
| `make` / `make help` | Print Makefile targets |
| `make setup` | `make config` + `pdm install` |
| `make config` | Create `.env` from `.env.example` if missing |
| `make lock` | Refresh `pdm.lock` after dependency changes |
| `make sync` | Install exactly what `pdm.lock` specifies |
| `make test` | Pytest (unit + e2e; integration skips if `DATABASE_URL` unset) |
| `make ci-local` | Ephemeral Postgres **16** + migrations **001**/**002** + Ruff + pytest; tears down container when finished (even on failure) |
| `make ci-local-stop` | Remove the **`ci-local`** Postgres container (e.g. after **`ci-local-postgres`** alone) |
| `make test-unit` | `pytest -m unit` |
| `make test-integration` | `pytest -m integration` (requires `DATABASE_URL` + migrations) |
| `make test-e2e` | `pytest -m e2e` (Docker compose config + ASGI smoke; compose test needs `docker` on `PATH`) |
| `make test-api` | `pytest -m api` |
| `make lint` | Ruff check |
| `make format` | Ruff format |
| `make clean` | Drop local build/caches (`.pytest_cache`, `.ruff_cache`, etc.) |
| `make resources` | Placeholder for future asset downloads |

| Command | Purpose |
|--------|---------|
| `pdm run python -m pytest` | Same as `make test` (avoids missing `.venv/bin/pytest` on some setups) |
| `pdm run python -m pytest -m "unit or integration"` | Typical CI subset (with `DATABASE_URL` set) |
| `pdm run python -m pytest --cov=verifiedsignal` | Tests with coverage (pytest-cov installed) |
| `pdm run api` / `pdm run api-prod` | Uvicorn (`app.main:app`) |
| `pdm run worker` | ARQ worker (`worker.main.WorkerSettings`) |
| `pdm run ruff check src tests app worker` | Same as `make lint` |
| `pdm run ruff format src tests app worker` | Same as `make format` |

### Docker and Compose

| Command | Purpose |
|--------|---------|
| `make docker-build` | Build the **app** image (`verifiedsignal:local`) |
| `make docker-up` | `make config`, then **`docker compose up --build`** (full stack in the **foreground**) |
| `make docker-down` | `docker compose down` (stops services; keeps volumes) |
| `make docker-test` | `make config`, build, then **`docker compose --profile test run --rm test`** (pytest in Docker) |
| `make docker-run` | `make config`, build, then **`docker compose run --rm app`** (one-off app; Compose starts dependencies) |

| Command | Purpose |
|--------|---------|
| `docker compose up -d` | Full stack in the **background** |
| `docker compose up -d postgres redis minio opensearch opensearch-dashboards` | **Infrastructure only** (no `app` container) |
| `docker compose up -d --build app worker` | API + worker + their dependencies |
| `docker compose ps` | Service status |
| `docker compose logs -f app` | Follow logs for `app` (replace `app` with any service name) |
| `docker compose logs -f opensearch opensearch-dashboards` | Follow OpenSearch-related logs |
| `docker compose --profile test run --rm test` | Pytest container without going through Make |
| `docker compose run --rm app pdm run verifiedsignal -- --help` | Legacy CLI inside the app image |
| `docker compose logs -f worker` | Worker logs |
| `docker compose down -v` | Stop and **remove named volumes** (wipes Postgres/Redis/MinIO/OpenSearch data) |
| `docker compose pull` | Pull newer infra images (MinIO, OpenSearch, etc.) |
| `docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/001_initial_schema.up.sql` | Apply initial DB schema (from repo root; see [`db/README.md`](db/README.md)) |

### Local URLs (default ports)

| Service | URL |
|--------|-----|
| MinIO console | [http://localhost:9001](http://localhost:9001) |
| MinIO S3 API | `http://localhost:9000` |
| OpenSearch REST | [http://localhost:9200](http://localhost:9200) |
| OpenSearch Dashboards | [http://localhost:5601](http://localhost:5601) |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| VerifiedSignal API (Compose `app`) | [http://localhost:8000](http://localhost:8000) (`/api/v1/...`) |

## Makefile reference

Run `make` or `make help` to print this list from the Makefile.

| Target | Description |
|--------|-------------|
| `make setup` | Runs `make config`, then `pdm install` (requires `pdm` on `PATH`) |
| `make lock` | Regenerates `pdm.lock` from `pyproject.toml` |
| `make sync` / `make install` | Installs exactly what `pdm.lock` specifies |
| `make test` | `pdm run python -m pytest` (see `make test-unit`, `test-integration`, `test-e2e`) |
| `make ci-local` | CI-like Postgres + migrations + Ruff + pytest; auto-removes container on exit |
| `make ci-local-stop` | Tear down **`ci-local`** Postgres container manually |
| `make test-unit` | `pdm run python -m pytest -m unit` |
| `make test-integration` | `pdm run python -m pytest -m integration` |
| `make test-e2e` | `pdm run python -m pytest -m e2e` |
| `make lint` | `pdm run python -m ruff check src tests app worker` |
| `make format` | `pdm run python -m ruff format src tests app worker` |
| `make clean` | Removes common build and cache directories |
| `make config` | Copies `.env.example` → `.env` only if `.env` is missing |
| `make resources` | Placeholder for future asset or download steps |
| `make docker-build` | `docker compose build` |
| `make docker-up` | `make config`, then **`docker compose up --build`** (full stack: infra + **app** + **worker**) |
| `make docker-down` | `docker compose down` |
| `make docker-test` | `make config`, build image, then run the `test` service (pytest in Docker) |
| `make docker-run` | `make config`, build image, then one-off `app` container |

Make variables **`PDM`** and **`DOCKER_COMPOSE`** default to `pdm` and `docker compose`; override them if your install paths or Compose wrapper differ.

## PDM without Make

Typical commands:

```bash
pdm install              # install project + dev dependencies from lockfile
pdm lock                 # update pdm.lock after changing pyproject.toml
pdm add <package>        # add a runtime dependency
pdm add -dG dev <pkg>    # add a dev dependency to the `dev` group
pdm run python -m pytest
pdm run python -m ruff check src tests app worker
pdm run python -m ruff format src tests app worker
```

Runtime dependencies live under `[project]` in `pyproject.toml`. Development tools (pytest, ruff, etc.) live in `[dependency-groups]` under `dev`.

## Docker Compose

The stack is defined in `docker-compose.yml`. **`make docker-up`** (or `docker compose up`) starts every service below except **`test`**, which uses the **`test`** profile.

| Service | Role | Default host port |
|--------|------|-------------------|
| **postgres** | Canonical relational data (PostgreSQL 16) | `5432` |
| **redis** | Pub/sub, caching, worker coordination (Redis 7, AOF on) | `6379` |
| **minio** | S3-compatible object storage (API + web console) | `9000` (API), `9001` (console) |
| **opensearch** | Search and analytics (single-node; `DISABLE_SECURITY_PLUGIN=true` for local dev only) | `9200` |
| **opensearch-dashboards** | OpenSearch Dashboards UI | `5601` |
| **app** | **FastAPI** (`pdm run api-prod` → uvicorn `app.main:app`) | **`8000`** → `API_PORT` |
| **worker** | **ARQ** consumer (`pdm run worker`) | — |
| **test** | Runs `pytest` in a one-off container (`profile: test`) | — |

The **app** service waits for **postgres** and **redis** only (MinIO/OpenSearch are optional for the current API scaffold). Env vars follow **`.env.example`** (`DATABASE_URL`, `REDIS_URL`, `USE_FAKE_QUEUE`, etc.).

**OpenSearch:** the cluster runs with the security plugin disabled via `DISABLE_SECURITY_PLUGIN=true` in Compose—suitable only for trusted local machines; do not expose these ports on a network. On **Linux**, if the node fails to start, raise `vm.max_map_count` (for example `sudo sysctl -w vm.max_map_count=262144`). See the [OpenSearch Docker install notes](https://opensearch.org/docs/latest/install-and-configure/install-opensearch/docker/).

**MinIO:** open `http://localhost:9001` and sign in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env` (defaults match the example file). Create a bucket named like `S3_BUCKET` (`verifiedsignal` by default) when you begin storing objects.

`.env` is optional: **`app`** and **`test`** use `env_file` with `required: false`. Compose still applies defaults from `docker-compose.yml` when variables are unset. Run **`make config`** to create `.env` from **`.env.example`** so host port overrides and credentials stay consistent.

For a consolidated command list, see **[Useful commands](#useful-commands)** above.

## Configuration and environment

- **`.env.example`** — template for local and Compose-related variables (Postgres, Redis, MinIO/S3, OpenSearch ports, `DATABASE_URL`, `REDIS_URL`, etc.). **`make config`** copies it to **`.env`** when `.env` is missing.
- **`VERIFIEDSIGNAL_CONFIG_DIR`** — directory the CLI treats as the config root (default `config` if unset). Under Compose it is set to `/app/config` inside the container.
- **`config/`** — mount point for configuration files. **`config/application.example.yml`** is a sample; copy or adapt it for your own `application.yml` (or other files) as the product grows.
- **Database** — apply **`db/migrations/001_initial_schema.up.sql`** against your Postgres (see [`db/README.md`](db/README.md)). **`DATABASE_URL`** in `.env` should point at that database.

Do not commit secrets. `.env` is gitignored.

## Project layout

```
├── Makefile
├── docker-compose.yml
├── Dockerfile
├── .dockerignore
├── .env.example
├── pyproject.toml
├── pdm.lock
├── .github/workflows/      # CI (Postgres + migrations + pytest + ruff)
├── app/                    # FastAPI (API routes, services, db session, schemas)
├── worker/                 # ARQ worker (tasks, pipeline scaffold)
├── db/
│   ├── README.md           # schema docs + apply/rollback examples
│   └── migrations/         # *.up.sql / *.down.sql
├── src/verifiedsignal/            # CLI package
├── tests/                  # pytest; see tests/README.md
└── config/                 # runtime configuration (mounted in Docker)
```

## License

See [LICENSE](LICENSE).
