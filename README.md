# VerifiedSignal

A document intelligence platform. This repository uses **Python** with **[PDM](https://pdm-project.org/latest/)** for dependencies, a **Makefile** for setup and common tasks, and **Docker Compose** for local infrastructure. **PostgreSQL** is the system-of-record; **OpenSearch** is a derived, disposable index; a **FastAPI** service exposes synchronous HTTP + **SSE**; an **ARQ** worker runs async background jobs on **Redis**.

## What’s included so far

This repo is an **early scaffold** with the following in place:

- **CLI package** — Python **3.11+**, `src/verifiedsignal/`, small CLI (`pdm run python -m verifiedsignal`, `pdm run verifiedsignal`).
- **Supabase session auth (optional)** — FastAPI routes under `**/auth`** (signup, login with **httpOnly** refresh cookie on path `/auth`, refresh, logout, reset email, `**POST /auth/sync-identity`**); JWT validation via **JWKS** or **HS256** (`app/auth/`). Bearer requests can **auto-provision** Postgres `**users`** + personal **org** + **Inbox** collection from the JWT `sub`. Protected examples: `**/api/v1/documents`**, `**/api/v1/collections**`, `**/api/v1/users/me**`. See `**[docs/end-user/README.md](docs/end-user/README.md)**` (end-user guide), `**[docs/auth-supabase.md](docs/auth-supabase.md)**`, `**[docs/tenancy-postgres.md](docs/tenancy-postgres.md)**`, `**[docs/accounts-and-collections.md](docs/accounts-and-collections.md)**` (short pointer), `**[supabase/README.md](supabase/README.md)**`, and `**apps/web/README.md**` for the React/Vite side (`**VITE_API_URL**` enables API-backed dashboard, documents, upload (including **local folder** tree + client-side sync on `/library/upload`), search, collections, collection analytics, SSE + pipeline polling on upload/dashboard, and `**canonical_score**` on document detail; mock demo when unset).
- **HTTP API** — root package `**app/`**: **FastAPI** (`app/main.py`), `**/api/v1`** routes for **health** (Postgres, Redis, object storage, OpenSearch reachability), info, **Phase 1 document intake** (`POST /api/v1/documents` multipart upload → Postgres + MinIO/S3 + ARQ), **keyword search** (`GET /api/v1/search` over OpenSearch or `**USE_FAKE_OPENSEARCH`** in tests; **Bearer required** by default), **collection analytics** (`GET /api/v1/collections/{id}/analytics` — index facets + Postgres score rollups), **document pipeline status** (`GET /api/v1/documents/{id}/pipeline`), **signed original download** (`GET /api/v1/documents/{id}/file` — presigned redirect or streamed), and **SSE** (`/api/v1/events/stream`; **JWT** via `**Authorization`** or `**?access_token=**` by default). **SQLAlchemy** session factory for Postgres (`app/db/session.py`); JWT validation and dependencies in `**app/auth/dependencies.py`** (Supabase-compatible); `**app/auth/placeholder.py**` is legacy/minimal.
- **Worker** — root package `**worker/`**: **[ARQ](https://arq-docs.helpmanual.io/)** worker on Redis (`pdm run worker`), `process_document` runs scaffold stages: **ingest** (storage head check), **extract** (PDF/DOCX/plain → `**documents.body_text`** + optional `**extract_artifact_key**` artifact), **enrich** (text stats on `**body_text`** in `**pipeline_events**`), **score** (canonical **heuristic** row in `**document_scores`**, plus optional `**score_document**` job when `**ENQUEUE_SCORE_AFTER_PIPELINE=true**` — **stub** or **HTTP** remote scorer per `**SCORE_ASYNC_BACKEND`** / `**SCORE_HTTP_URL**`, retries + idempotency; see `**[docs/scoring-http.md](docs/scoring-http.md)**`; remote scorer contract: `**[docs/external-scorer-implementation-guide.md](docs/external-scorer-implementation-guide.md)**`), **index** (OpenSearch), **finalize**. See `**[docs/pipeline-stages.md](docs/pipeline-stages.md)`**. **Vector** search and **in-process LLM** calls are still future work; HTTP scoring delegates to **your** model service.
- **PDM** — `pyproject.toml`, `**pdm.lock`**, scripts: `**pdm run api**` (uvicorn reload), `**pdm run api-prod**`, `**pdm run worker**`, `**pdm run reference-http-scorer**` (minimal FastAPI scorer for `**SCORE_ASYNC_BACKEND=http**` — see `**[docs/scoring-http.md](docs/scoring-http.md)**`), dev group (**pytest**, **ruff**, etc.).
- **Makefile** — `setup`, `lock` / `sync`, `test` / `test-unit` / `test-integration` / `test-e2e` / `**test-api`**, `**ci-local**` / `**ci-local-stop**`, `lint`, `format`, Docker targets.
- **Tests** — `**pytest`** markers: `**unit**`, `**integration**`, `**e2e**`, `**api**`. See `**[tests/README.md](tests/README.md)**`.
- **CI** — `**[.github/workflows/ci.yml](.github/workflows/ci.yml)`** — **Python** job: Ruff on `src`, `tests`, `app`, `worker`, `**scripts`**; `**pip-audit**` on exported requirements; Postgres **16** + migrations; `**pytest`** with `**--cov=app/services**` (line coverage floor **45%** via `**pyproject.toml`** `[tool.coverage.report]`, `**term-missing**` + `**coverage.xml**` artifact). **Web** job: `**apps/web`** — `npm ci`, `**npm audit**`, Playwright Chromium, `**npm run build**`, `**test:unit**`, `**test:e2e**`, `**test:e2e:api-mock**`. **Dependabot** — `**[.github/dependabot.yml](.github/dependabot.yml)`** for **GitHub Actions**, **pip** (root / PDM lock), and `**apps/web`** npm.
- **Security / hardening (high level)** — `**ENVIRONMENT=staging`** is treated like production for **client-visible** surfaces: `**/health`** omits dependency error/DSN detail, and **Swagger/OpenAPI** stay off unless `**EXPOSE_OPENAPI_DOCS=true`**. `**ENVIRONMENT=production|prod**` additionally logs startup warnings for `**USE_FAKE_***` and for `**VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK=true**` (risky multi-tenant default). `**VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK**` defaults to `**false**`; set `**true**` in `**.env.example`-style** local dev when you rely on the seeded default inbox. Per-IP **rate limits** (**slowapi**) apply to `**/auth/*`** and document intake (`**RATE_LIMIT_***`, `**RATE_LIMIT_ENABLED**` in `**.env.example**`); limits are **in-memory per API process** (not shared across replicas). For local commands that mirror CI dependency audits, see **[Dependency security](#dependency-security)** below.
- **Docker** — `**Dockerfile`** copies `app/`, `worker/`, `src/`, `tests/`, `db/`, sets `**PYTHONPATH=/app**`, default CMD `**api-prod**` (uvicorn).
- **Docker Compose** — infra + runtimes:
  - **PostgreSQL**, **Redis**, **MinIO**, **OpenSearch**, **Dashboards**
  - `**app`** — FastAPI on `**8000**` (depends on **postgres** + **redis**)
  - `**worker`** — ARQ consumer (depends on **redis**)
  - `**test`** — pytest (**profile:** `test`)
- **Configuration** — `**.env.example`** (ports, DB/Redis/S3/OpenSearch URLs), `**config/application.example.yml**`, `**config/**` mounted read-only into the app container.
- **Canonical database schema** — SQL migrations under `**db/migrations/`** (users, organizations, collections, documents, sources, pipeline runs/events, document scores). See `**[db/README.md](db/README.md)**` for how to apply them and architectural notes (Postgres as source of truth, OpenSearch as disposable index).
- **Design (metadata & tagging)** — `**[docs/document-metadata-design.md](docs/document-metadata-design.md)`** specifies user vs pipeline metadata, `**document_tags**`, pipeline stage writers, API sketch, and OpenSearch denormalization (appendix DDL; implement as a future migration when ready).

## Prerequisites

- **Python** 3.11 or newer
- **[PDM](https://pdm-project.org/latest/#installation)** on your `PATH` (`pdm --version`)
- **GNU Make**
- **Docker** and **Docker Compose** v2 (`docker compose version`) if you use the container workflow

## Dependency security

CI runs `**pip-audit`** on exported Python requirements and `**npm audit**` in `**apps/web**` (see `**[.github/workflows/ci.yml](.github/workflows/ci.yml)**`). Advisory databases and transitive pins change over time, so refresh locks occasionally—e.g. `**pdm lock**` / `**pdm update**` for Python and `**npm update**` or Dependabot PRs for the web app—even when audits are currently clean.

To mirror the Python audit locally:

```bash
pdm export -f requirements --without-hashes -o /tmp/requirements-audit.txt
pdm run pip-audit -r /tmp/requirements-audit.txt
```

For the web UI:

```bash
cd apps/web && npm audit
```

If you use `**uv**` with the repo’s `**uv.lock**`, keep that lockfile aligned with `**pyproject.toml**` (e.g. `**uv lock**`) and run your usual `**uv**`-based audit; CI uses **PDM** and does not validate `**uv.lock`**.

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
4. Run tests and linters:
  ```bash
   make test
   make lint
  ```
   For a **full suite on your machine** (including integration tests against real Postgres), see **[Testing locally](#testing-locally)** below.

## Local development workflow (recommended)

Use **`make dev`** (alias: **`make local`**) for day-to-day work so Postgres, Redis, MinIO, OpenSearch, and OpenSearch Dashboards all come up on the host ports the API expects, then **FastAPI** runs on the host with reload (same env wiring as **`make api-local`**).

### Steps

1. **Once:** `make setup` (dependencies + `.env` from `.env.example` if missing).
2. **Terminal 1 — API + infra:** from the repo root, run:
   ```bash
   make dev
   ```
   This runs **`make dev-stack`** (Docker Compose **postgres**, **redis**, **minio**, **opensearch**, **opensearch-dashboards**; waits until each dependency is healthy), then starts **`make api-local`** on **`0.0.0.0:8000`** by default. Health check: `curl -s http://127.0.0.1:8000/api/v1/health | jq`.
3. **First time only (empty database):** in another terminal, apply schema migrations:
   ```bash
   make migrate
   ```
   Skip if migrations are already applied (see **`[db/README.md](db/README.md)`** if `001` already exists).
4. **Supabase auth (`/auth/*`, sign-in in the SPA):** the Makefile does not start the Supabase CLI. When you need local GoTrue, run **`supabase start`** from **`./supabase`** (see **`[supabase/README.md](supabase/README.md)`**). With the API **on the host**, **`SUPABASE_URL`** is typically **`http://127.0.0.1:54321`** (see **`[docs/auth-supabase.md](docs/auth-supabase.md)`** and **`.env.example`**).
5. **Terminal 2 — Web UI:**
   ```bash
   make web-dev
   ```
   Open the URL Vite prints (often **`http://127.0.0.1:5173`**). Ensure **`apps/web/.env.local`** sets **`VITE_API_URL`** to your API (e.g. **`http://127.0.0.1:8000`**); **`make web-config`** creates it from **`apps/web/.env.example`** if missing.
6. **Optional — background jobs:** for URL ingest, pipeline stages, and ARQ queues with a real Redis (not **`USE_FAKE_QUEUE`**), run in another terminal:
   ```bash
   pdm run worker
   ```

### Related Makefile targets

| Command | Purpose |
| ------- | ------- |
| **`make dev-stack`** | Infra only + health waits; then run **`make api-local`** yourself when you want the API separate from stack bring-up. |
| **`make dev-down`** | **`docker compose stop`** on the dev-stack services (keeps volumes; does not stop Compose **app** / **worker** if you use **`make docker-up`**). |
| **`make api-local`** | Postgres (Compose) + API only. Use after **`make dev-stack`** if Redis / MinIO / OpenSearch were not already running. |
| **`make api-local-restart LOCAL_API_PG_PORT=5433`** | Frees the API port and restarts **`api-local`**, forwarding **`LOCAL_API_PG_PORT`** / **`LOCAL_API_PORT`** so **`DATABASE_URL`** matches Compose Postgres. |

Override the Postgres host port when **5432** is taken, for example:

```bash
make dev LOCAL_API_PG_PORT=5433
```

Whenever you use a non-default Postgres host port, pass the same **`LOCAL_API_PG_PORT`** for **`make dev`**, **`make dev-stack`**, and **`make api-local`** so Compose publishes Postgres on that port and the API’s **`DATABASE_URL`** matches. **`make migrate`** runs **`psql`** inside the Compose **`postgres`** container (no host port in the DSN).

### Alternative: full stack in Docker

To run the **API** and **worker** inside Compose as well, use **`make docker-up`** (builds images; heavier). Configure **Supabase** for auth (local **`SUPABASE_URL=http://127.0.0.1:54321`** is rewritten to **`host.docker.internal`** inside the **`app`** container); see **[Web UI against the Docker API](#web-ui-against-the-docker-api)** below.

## Testing locally

### Quick run (no Postgres)

After `**make setup`**:

```bash
make test    # unit, e2e, api; integration skips if DATABASE_URL is unset
make lint
```

Integration tests that need a database are skipped unless `**DATABASE_URL**` is set and migrations **001** through **005** are applied. Markers and behavior are described in `**[tests/README.md](tests/README.md)`**.

### Full suite like CI (ephemeral Postgres in Docker)

`**[Makefile](Makefile)**` includes targets that mirror **GitHub Actions**: **Postgres 16**, same user/password/database as CI, migrations **001**–**005**, then **Ruff** (including `**scripts/`**) and **pytest** with `**--cov=app/services`** and the correct `**DATABASE_URL**`.

```bash
make setup          # once: dependencies + .env from example if missing
make ci-local       # ephemeral Postgres + migrations + lint + pytest; **removes the container when done** (including on failure)
make ci-local-stop  # optional: remove the container if you started Postgres without a full ci-local run
```

- Requires **Docker** on your `PATH`. By default the DB is published on host port `**5433`** so `**make ci-local**` does not fight **Compose Postgres** on **5432**. To use **5432** instead (when it is free):
  ```bash
  make ci-local CI_LOCAL_PG_PORT=5432
  ```
- `**make ci-local**` removes any existing container named `**verifiedsignal-ci-postgres**` (see `**CI_LOCAL_PG_CONTAINER**` in the Makefile) before starting, and **removes it again on exit** (success or failure) so the next run is not blocked on the port.
- `**DATABASE_URL` in the process environment** (as set by `**make ci-local`**) takes precedence over `**.env**` for the running app, so SQLAlchemy and `**psycopg**` in tests use the same DSN. If you previously saw “password authentication failed” only on `**POST /documents**` while other integration tests passed, a mismatched `**.env**` was the usual cause.

### Compose Postgres (reuse your dev database)

If you prefer the project’s **Compose** Postgres:

```bash
docker compose up -d postgres
```

Apply **001** through **005** from the repo root (examples in `**[db/README.md](db/README.md)`**), or run `**make migrate**` when using Compose Postgres, then point `**DATABASE_URL**` at the instance (typically `**postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal**` from the host) and run:

```bash
make test
# or only integration-marked tests:
make test-integration
```

### Tests inside Docker

`**make docker-test**` builds the app image and runs **pytest** in the Compose `**test`** service (see **[Useful commands](#useful-commands)**).

## HTTP API and worker (local)

**Why separate runtimes?** The API process optimizes for **low-latency request/response**, **SSE**, and **auth** at the edge. Workers optimize for **long-running**, **CPU/IO-heavy** steps (extract, score, bulk index) without blocking clients. Redis/ARQ decouples them so you can scale API and worker tiers independently and restart workers without dropping HTTP availability.

**Phase 1 intake (implemented):** `POST /api/v1/documents` accepts **multipart/form-data** with a file. The API validates input, inserts a canonical `**documents`** row in `**created**`, uploads bytes to **S3-compatible storage** (MinIO locally) under `raw/{document_id}/{safe_filename}`, updates the row to `**queued`**, inserts `**document_sources**` with an `s3://{bucket}/{key}` locator, then enqueues `**process_document**` on ARQ. If enqueue fails, the row stays `**queued**` with `**enqueue_error**` set; the object and Postgres metadata are kept.

**URL intake (implemented):** `POST /api/v1/documents/from-url` (JSON) validates the URL (SSRF mitigations), inserts a `**created`** row plus a `**document_sources**` row with `**source_kind: url**`, and enqueues `**fetch_url_and_ingest**`. The worker streams the response into storage, then matches the multipart path (`queued` + `**process_document**`). Details, env vars, and security notes: `**[docs/url-ingest.md](docs/url-ingest.md)**`.

**Still stubbed / later stages:** **First-party** LLM scoring inside this repo (today: **heuristic** in-pipeline + optional async `**score_document`**: **stub** or **operator HTTP** endpoint — `**[docs/scoring-http.md](docs/scoring-http.md)`**), **vector** search. **SSE** uses **Redis pub/sub** (same `**REDIS_URL`** as ARQ) so multiple API replicas share `**GET /api/v1/events/stream**` traffic; `**USE_FAKE_EVENT_HUB=true**` keeps an in-process hub for tests. The SPA also **polls** `**GET /api/v1/documents/{id}/pipeline`** for worker progress. **Keyword search** uses **text extract** (PDF/DOCX/plain) + **OpenSearch** (or `**USE_FAKE_OPENSEARCH`**). Pipeline persistence: `**pipeline_runs**` / `**pipeline_events**`; optional `**ENQUEUE_SCORE_AFTER_PIPELINE**` queues `**score_document**` (ARQ `**max_tries=5**` on transient scorer failures).

**Near-term (keep in mind):** **Bayesian fusion** for ratings — treat `**ai_generation_probability`** / related fields as updatable **posteriors** (prior + likelihoods from heuristic, HTTP scorer, and future signals). Not implemented yet; sketched under `**[docs/scoring-http.md](docs/scoring-http.md)`** (*Planned: Bayesian fusion*). Target for design + first slice: **~next week**.

**Search + SSE auth:** `**VERIFIEDSIGNAL_REQUIRE_AUTH_SEARCH*`* and `**VERIFIEDSIGNAL_REQUIRE_AUTH_SSE**` (default **true**) enforce Bearer JWT for `**GET /api/v1/search`** and `**GET /api/v1/events/stream**` (browsers: `**?access_token=**` on the stream). SSE events are filtered by `**payload.auth_sub**`. See `**[docs/end-user/search-and-events.md](docs/end-user/search-and-events.md)**`.

### Run the API (uvicorn)

From the repo root (PDM puts the project on `PYTHONPATH`):

```bash
make setup
export DATABASE_URL=postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal
# Apply migrations 001–005 — see db/README.md
export REDIS_URL=redis://localhost:6379/0
export OPENSEARCH_URL=http://127.0.0.1:9200
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

Requires **Redis** and `**USE_FAKE_QUEUE` unset/false** for the API when you want real enqueue:

```bash
export REDIS_URL=redis://localhost:6379/0
pdm run worker
```

**HTTP async scoring (optional):** To exercise `**ENQUEUE_SCORE_AFTER_PIPELINE=true`** and `**SCORE_ASYNC_BACKEND=http**` without an external API, start `**pdm run reference-http-scorer**` in another terminal and set `**SCORE_HTTP_URL=http://127.0.0.1:9100/score**` on the worker (and matching bearer tokens if you enable them). Step-by-step: `**[docs/scoring-http.md](docs/scoring-http.md)**` (*Reference HTTP scorer*).

### MinIO locally (object storage)

Start MinIO (Docker example):

```bash
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  quay.io/minio/minio server /data --console-address ":9001"
```

Create the `**verifiedsignal**` bucket once (Console at [http://127.0.0.1:9001](http://127.0.0.1:9001), or `**mc**`). The `**S3ObjectStorage**` adapter attempts `**create_bucket**` if `**head_bucket**` reports a missing bucket (simple dev convenience; production often provisions buckets out-of-band).

Point the API at MinIO with `**S3_ENDPOINT_URL**` (e.g. `http://127.0.0.1:9000`) and `**S3_USE_PATH_STYLE=true**`.

### Minimal API checks

**OpenAPI:** Swagger UI is served at the **root** (`http://127.0.0.1:8000/`). Machine-readable schema: `**GET /openapi.json`**. Alternative docs: `**/redoc**`. Legacy path `**/docs**` redirects to `**/**`.

```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq
# Intake and search need a Bearer access token from POST /auth/login (see docs/auth-supabase.md).
# export TOKEN='eyJ...'
curl -s -X POST http://127.0.0.1:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./README.md;type=text/markdown" \
  -F "title=Demo upload" | jq
# Optional explicit collection (otherwise VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID / seeded default-inbox)
# -F "collection_id=00000000-0000-4000-8000-000000000002"
```

SSE (streams until Ctrl+C; same `**$TOKEN**`, or `**?access_token=**` if you cannot send a header):

```bash
curl -N -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/events/stream
# curl -N "http://127.0.0.1:8000/api/v1/events/stream?access_token=$TOKEN"
```

## Useful commands

### Local development


| Command                 | Purpose                                                                                                                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `make` / `make help`    | Print Makefile targets                                                                                                                                                               |
| `make setup`            | `make config` + `pdm install`                                                                                                                                                        |
| `make install-supabase` | Install **Supabase CLI** via Homebrew when `brew` is available (else prints hints; see **`supabase/README.md`**)                                                                     |
| `make config`           | Create `.env` from `.env.example` if missing                                                                                                                                         |
| `make lock`             | Refresh `pdm.lock` after dependency changes                                                                                                                                          |
| `make sync`             | Install exactly what `pdm.lock` specifies                                                                                                                                            |
| `make test`             | Pytest (unit + e2e; integration skips if `DATABASE_URL` unset)                                                                                                                       |
| `make ci-local`         | Ephemeral Postgres **16** + migrations **001**–**005** + Ruff (`**scripts/`** included) + pytest with `**--cov=app/services**`; tears down container when finished (even on failure) |
| `make ci-local-stop`    | Remove the `**ci-local**` Postgres container (e.g. after `**ci-local-postgres**` alone)                                                                                              |
| `make test-unit`        | `pytest -m unit`                                                                                                                                                                     |
| `make test-integration` | `pytest -m integration` (requires `DATABASE_URL` + migrations)                                                                                                                       |
| `make test-e2e`         | `pytest -m e2e` (Docker compose config + ASGI smoke; compose test needs `docker` on `PATH`)                                                                                          |
| `make test-api`         | `pytest -m api`                                                                                                                                                                      |
| `make lint`             | Ruff check                                                                                                                                                                           |
| `make format`           | Ruff format                                                                                                                                                                          |
| `make clean`            | Drop local build/caches (`.pytest_cache`, `.ruff_cache`, etc.)                                                                                                                       |
| `make resources`        | Placeholder for future asset downloads                                                                                                                                               |
| `make web-config`       | Create `**apps/web/.env.local**` from `**apps/web/.env.example**` if missing (API mode → `**http://127.0.0.1:8000**`)                                                                |
| `make web-dev`          | Run `**web-config**`, then Vite dev server in `**apps/web**` (install deps with `**npm install**` there first)                                                                       |
| `make dev-stack`        | Compose: Postgres + Redis + MinIO + OpenSearch + Dashboards; waits until healthy (uses **`LOCAL_API_*`** ports)                                                                     |
| `make dev`              | **`dev-stack`** then **`make api-local`** (host API with reload; see [Local development workflow](#local-development-workflow-recommended))                                         |
| `make local`            | Alias for **`make dev`**                                                                                                                                                            |
| `make dev-down`         | Stop dev-stack services only (volumes kept)                                                                                                                                         |
| `make api-local`        | Compose Postgres + host FastAPI (use **`dev-stack`** first if Redis / MinIO / OpenSearch are not up)                                                                                |
| `make api-local-restart` | Kill listener on **`LOCAL_API_PORT`**, then **`api-local`** (forwards **`LOCAL_API_PG_PORT`** / **`LOCAL_API_PORT`**)                                                               |



| Command                                                                 | Purpose                                                                |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `pdm run python -m pytest`                                              | Same as `make test` (avoids missing `.venv/bin/pytest` on some setups) |
| `pdm run python -m pytest -m "unit or integration"`                     | Typical CI subset (with `DATABASE_URL` set)                            |
| `pdm run python -m pytest --cov=app/services --cov-report=term-missing` | Same coverage target as CI (`**fail_under**` in `**pyproject.toml**`)  |
| `pdm run api` / `pdm run api-prod`                                      | Uvicorn (`app.main:app`)                                               |
| `pdm run worker`                                                        | ARQ worker (`worker.main.WorkerSettings`)                              |
| `pdm run ruff check src tests app worker scripts`                       | Same as `make lint`                                                    |
| `pdm run ruff format src tests app worker scripts`                      | Same as `make format`                                                  |


### Docker and Compose


| Command             | Purpose                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------- |
| `make docker-build` | Build the **app** image (`verifiedsignal:local`)                                                        |
| `make docker-up`    | `make config`, then `**docker compose up --build`** (full stack in the **foreground**)                  |
| `make docker-down`  | `docker compose down` (stops services; keeps volumes)                                                   |
| `make docker-test`  | `make config`, build, then `**docker compose --profile test run --rm test`** (pytest in Docker)         |
| `make docker-run`   | `make config`, build, then `**docker compose run --rm app**` (one-off app; Compose starts dependencies) |



| Command                                                                                                                                 | Purpose                                                                        |
| --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `docker compose up -d`                                                                                                                  | Full stack in the **background**                                               |
| `docker compose up -d postgres redis minio opensearch opensearch-dashboards`                                                            | **Infrastructure only** (no `app` container)                                   |
| `docker compose up -d --build app worker`                                                                                               | API + worker + their dependencies                                              |
| `docker compose ps`                                                                                                                     | Service status                                                                 |
| `docker compose logs -f app`                                                                                                            | Follow logs for `app` (replace `app` with any service name)                    |
| `docker compose logs -f opensearch opensearch-dashboards`                                                                               | Follow OpenSearch-related logs                                                 |
| `docker compose --profile test run --rm test`                                                                                           | Pytest container without going through Make                                    |
| `docker compose run --rm app pdm run verifiedsignal -- --help`                                                                          | Legacy CLI inside the app image                                                |
| `docker compose logs -f worker`                                                                                                         | Worker logs                                                                    |
| `docker compose down -v`                                                                                                                | Stop and **remove named volumes** (wipes Postgres/Redis/MinIO/OpenSearch data) |
| `docker compose pull`                                                                                                                   | Pull newer infra images (MinIO, OpenSearch, etc.)                              |
| `docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/001_initial_schema.up.sql` | Apply initial DB schema (from repo root; see `[db/README.md](db/README.md)`)   |


### Local URLs (default ports)


| Service                            | URL                                                            |
| ---------------------------------- | -------------------------------------------------------------- |
| MinIO console                      | [http://localhost:9001](http://localhost:9001)                 |
| MinIO S3 API                       | `http://localhost:9000`                                        |
| OpenSearch REST                    | [http://localhost:9200](http://localhost:9200)                 |
| OpenSearch Dashboards              | [http://localhost:5601](http://localhost:5601)                 |
| PostgreSQL                         | `localhost:5432`                                               |
| Redis                              | `localhost:6379`                                               |
| VerifiedSignal API (Compose `app`) | [http://localhost:8000](http://localhost:8000) (`/api/v1/...`) |


## Makefile reference

Run `make` or `make help` to print this list from the Makefile.


| Target                       | Description                                                                                                                 |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `make setup`                 | Runs `make config`, then `pdm install` (requires `pdm` on `PATH`)                                                           |
| `make install-supabase`      | Install **Supabase CLI** (Homebrew when available; see **`supabase/README.md`**)                                             |
| `make lock`                  | Regenerates `pdm.lock` from `pyproject.toml`                                                                                |
| `make sync` / `make install` | Installs exactly what `pdm.lock` specifies                                                                                  |
| `make test`                  | `pdm run python -m pytest` (see `make test-unit`, `test-integration`, `test-e2e`)                                           |
| `make ci-local`              | CI-like Postgres + migrations **001**–**005** + Ruff + pytest (`**app/services`** coverage); auto-removes container on exit |
| `make ci-local-stop`         | Tear down `**ci-local**` Postgres container manually                                                                        |
| `make test-unit`             | `pdm run python -m pytest -m unit`                                                                                          |
| `make test-integration`      | `pdm run python -m pytest -m integration`                                                                                   |
| `make test-e2e`              | `pdm run python -m pytest -m e2e`                                                                                           |
| `make lint`                  | `pdm run python -m ruff check src tests app worker scripts`                                                                 |
| `make format`                | `pdm run python -m ruff format src tests app worker scripts`                                                                |
| `make clean`                 | Removes common build and cache directories                                                                                  |
| `make config`                | Copies `.env.example` → `.env` only if `.env` is missing                                                                    |
| `make resources`             | Placeholder for future asset or download steps                                                                              |
| `make docker-build`          | `docker compose build`                                                                                                      |
| `make docker-up`             | `make config`, then `**docker compose up --build**` (full stack: infra + **app** + **worker**)                              |
| `make docker-down`           | `docker compose down`                                                                                                       |
| `make docker-test`           | `make config`, build image, then run the `test` service (pytest in Docker)                                                  |
| `make docker-run`            | `make config`, build image, then one-off `app` container                                                                    |
| `make web-config`            | Create `**apps/web/.env.local`** from `**apps/web/.env.example**` if missing                                                |
| `make web-dev`               | `**web-config**`, then `**npm run dev**` in `**apps/web**`                                                                  |
| `make dev-stack`             | Compose infra (Postgres, Redis, MinIO, OpenSearch, Dashboards) + readiness waits                                            |
| `make dev` / `make local`    | **`dev-stack`** + host uvicorn (**`api-local`**); recommended daily workflow                                                |
| `make dev-down`              | **`docker compose stop`** for dev-stack services only                                                                       |
| `make api-local-postgres`    | Compose Postgres on **`LOCAL_API_PG_PORT`** + **`pg_isready`** wait                                                         |
| `make api-local`             | **`api-local-postgres`** + **`pdm run`** uvicorn with **`API_LOCAL_ENV`** (127.0.0.1 service URLs)                          |
| `make api-local-prod`        | Same as **`api-local`** without **`--reload`**                                                                              |
| `make api-local-restart`     | Free **`LOCAL_API_PORT`**, then **`api-local`** (forwards **`LOCAL_API_PG_PORT`**, **`LOCAL_API_PORT`**)                    |


Make variables `**PDM**` and `**DOCKER_COMPOSE**` default to `pdm` and `docker compose`; override them if your install paths or Compose wrapper differ. For **`LOCAL_API_PG_PORT`**, **`LOCAL_API_PORT`**, and other host URLs, see **`[Makefile](Makefile)`** comments and [Local development workflow](#local-development-workflow-recommended).

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

The stack is defined in `docker-compose.yml`. `**make docker-up**` (or `docker compose up`) starts every service below except `**test**`, which uses the `**test**` profile.


| Service                   | Role                                                                                  | Default host port              |
| ------------------------- | ------------------------------------------------------------------------------------- | ------------------------------ |
| **postgres**              | Canonical relational data (PostgreSQL 16)                                             | `5432`                         |
| **redis**                 | Pub/sub, caching, worker coordination (Redis 7, AOF on)                               | `6379`                         |
| **minio**                 | S3-compatible object storage (API + web console)                                      | `9000` (API), `9001` (console) |
| **opensearch**            | Search and analytics (single-node; `DISABLE_SECURITY_PLUGIN=true` for local dev only) | `9200`                         |
| **opensearch-dashboards** | OpenSearch Dashboards UI                                                              | `5601`                         |
| **app**                   | **FastAPI** (`pdm run api-prod` → uvicorn `app.main:app`)                             | `**8000`** → `API_PORT`        |
| **worker**                | **ARQ** consumer (`pdm run worker`)                                                   | —                              |
| **test**                  | Runs `pytest` in a one-off container (`profile: test`)                                | —                              |


The **app** service waits for **postgres** and **redis** only (MinIO/OpenSearch are optional for the current API scaffold). Env vars follow `**.env.example`** (`DATABASE_URL`, `REDIS_URL`, `USE_FAKE_QUEUE`, etc.).

**OpenSearch:** the cluster runs with the security plugin disabled via `DISABLE_SECURITY_PLUGIN=true` in Compose—suitable only for trusted local machines; do not expose these ports on a network. On **Linux**, if the node fails to start, raise `vm.max_map_count` (for example `sudo sysctl -w vm.max_map_count=262144`). See the [OpenSearch Docker install notes](https://opensearch.org/docs/latest/install-and-configure/install-opensearch/docker/).

**MinIO:** open `http://localhost:9001` and sign in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env` (defaults match the example file). Create a bucket named like `S3_BUCKET` (`verifiedsignal` by default) when you begin storing objects.

`.env` is optional: `**app`** and `**test**` use `env_file` with `required: false`. Compose still applies defaults from `docker-compose.yml` when variables are unset. Run `**make config**` to create `.env` from `**.env.example**` so host port overrides and credentials stay consistent.

### Web UI against the Docker API

The React app lives in `**apps/web**` and is **not** part of Compose. To use **API mode** (real backend instead of mock demo data):

1. **Stack + DB** — `docker compose up -d --build` (or `**make docker-up`**), then apply migrations if needed (`**make migrate**` on a fresh volume, or `**make migrate-002**` … `**migrate-005**` if `**users` already exists**).
2. **Root `.env`** — After `**make config**`, keep `**CORS_ORIGINS**` and `**AUTH_COOKIE_SECURE**` as in `**.env.example**` so the browser can call `**http://127.0.0.1:8000**` from the Vite dev server with cookies. For **login/signup**, set Supabase vars from `**supabase status --output json**` (see **`supabase/README.md`**). Use **`SUPABASE_URL=http://127.0.0.1:54321`** for local GoTrue after **`supabase start`**; the API **rewrites loopback to `host.docker.internal` when it runs inside Docker**, so the same value works for **`pdm run api`** and Compose. Restart **`app`** after editing: **`docker compose up -d --build app`**.
3. **SPA env** — From the repo root, `**make web-config`** creates `**apps/web/.env.local**` from `**apps/web/.env.example**` if missing (sets `**VITE_API_URL=http://127.0.0.1:8000**`). Run `**cd apps/web && npm install**` once, then `**make web-dev**` or `**npm run dev**` and open the printed URL (typically `**http://127.0.0.1:5173**`).

Use `**127.0.0.1**` consistently for API and UI URLs in dev so CORS and cookie behavior match. Ensure the **MinIO** bucket named like `**S3_BUCKET`** exists if you use real uploads.

For a consolidated command list, see **[Useful commands](#useful-commands)** above.

## Configuration and environment

- `**.env.example`** — template for local and Compose-related variables (Postgres, Redis, MinIO/S3, OpenSearch ports, `DATABASE_URL`, `REDIS_URL`, etc.). `**make config**` copies it to `**.env**` when `.env` is missing.
- `**VERIFIEDSIGNAL_CONFIG_DIR**` — directory the CLI treats as the config root (default `config` if unset). Under Compose it is set to `/app/config` inside the container.
- `**config/**` — mount point for configuration files. `**config/application.example.yml**` is a sample; copy or adapt it for your own `application.yml` (or other files) as the product grows.
- **Database** — apply `**db/migrations/001_initial_schema.up.sql`** against your Postgres (see `[db/README.md](db/README.md)`). `**DATABASE_URL**` in `.env` should point at that database.

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
├── .github/workflows/      # CI (Postgres + migrations + pytest + coverage + ruff)
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

2026, CalgentiK

