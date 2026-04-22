# Developing locally

## Prerequisites

- Python 3.11+
- [PDM](https://pdm-project.org/latest/#installation) on your `PATH`
- GNU **Make**
- **Docker** and **Docker Compose** v2 if you use containers

## Quick start

```bash
git clone <repo-url> && cd verifiedsignal
make setup          # deps + .env from .env.example if missing
pdm run python -m verifiedsignal   # CLI
make test && make lint
```

For day-to-day API + infra, use **`make dev`** (see below). For **integration tests**, set `DATABASE_URL` and apply migrations — [tests/README.md](../tests/README.md), [db/README.md](../db/README.md).

## Recommended workflow (`make dev`)

1. **Once:** `make setup`.
2. **Terminal 1:** `make dev` — brings up Postgres, Redis, MinIO, OpenSearch, Dashboards (via Compose), then FastAPI with reload on `0.0.0.0:8000`. Health: `curl -s http://127.0.0.1:8000/api/v1/health | jq`.
3. **First-time DB:** `make migrate` (skip if schema already applied).
4. **Supabase (optional):** `supabase start` from `./supabase` when you need local GoTrue — [supabase/README.md](../supabase/README.md), [auth-supabase.md](auth-supabase.md). With API on host, `SUPABASE_URL` is often `http://127.0.0.1:54321`.
5. **Terminal 2 — web:** `make web-config` (creates `apps/web/.env.local` if needed), then `make web-dev`. Set `VITE_API_URL=http://127.0.0.1:8000` for API mode.
6. **Worker (optional):** `pdm run worker` when not using `USE_FAKE_QUEUE`.

**Non-default Postgres port** (e.g. 5433 busy):

```bash
make dev LOCAL_API_PG_PORT=5433
```

Use the same `LOCAL_API_PG_PORT` for `dev`, `dev-stack`, and `api-local`. `make migrate` runs `psql` inside the Compose `postgres` container.

**Full stack in Docker:** `make docker-up` — see [docker-compose.md](docker-compose.md).

Related targets: `make dev-stack`, `make dev-down`, `make api-local`, `make api-local-restart` — [commands.md](commands.md).

## Testing

### Without Postgres

```bash
make test    # unit, e2e, api; integration skipped if DATABASE_URL unset
make lint
```

### CI-like run (`ci-local`)

Ephemeral Postgres 16, migrations, Ruff, pytest with `app/services` coverage:

```bash
make ci-local
make ci-local-stop   # tear down container if needed
```

Default DB host port **5433** (avoids clashing with Compose on 5432). Override: `make ci-local CI_LOCAL_PG_PORT=5432`.

### Compose Postgres

```bash
docker compose up -d postgres
make migrate
export DATABASE_URL=postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal
make test
# or: make test-integration
```

### Tests in Docker

`make docker-test` — pytest in the Compose `test` service.

## HTTP API and worker

**Intake:** `POST /api/v1/documents` (multipart) → Postgres + S3-compatible storage + ARQ `process_document`.

**URL intake:** `POST /api/v1/documents/from-url` — [url-ingest.md](url-ingest.md).

**Scoring:** Heuristic in pipeline + optional async HTTP scorer — [scoring-http.md](scoring-http.md). **SSE:** Redis pub/sub (`REDIS_URL`) or `USE_FAKE_EVENT_HUB=true` in tests.

**Search + SSE auth:** `VERIFIEDSIGNAL_REQUIRE_AUTH_SEARCH` / `VERIFIEDSIGNAL_REQUIRE_AUTH_SSE` (default true) — [end-user/search-and-events.md](end-user/search-and-events.md).

### Run API (uvicorn)

```bash
make setup
export DATABASE_URL=postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal
export REDIS_URL=redis://localhost:6379/0
export OPENSEARCH_URL=http://127.0.0.1:9200
export S3_ENDPOINT_URL=http://127.0.0.1:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export S3_BUCKET=verifiedsignal
export S3_USE_PATH_STYLE=true
export USE_FAKE_QUEUE=true          # optional: no worker
# export USE_FAKE_STORAGE=true      # optional: in-memory objects

pdm run api        # reload
# pdm run api-prod # no reload
```

### Run worker

```bash
export REDIS_URL=redis://localhost:6379/0
pdm run worker
```

Reference scorer for HTTP mode: `pdm run reference-http-scorer` — [scoring-http.md](scoring-http.md).

### MinIO (example)

```bash
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  quay.io/minio/minio server /data --console-address ":9001"
```

Create bucket `verifiedsignal` (console at http://127.0.0.1:9001). Use `S3_ENDPOINT_URL` + `S3_USE_PATH_STYLE=true`.

### Quick API checks

Swagger UI at `/` (when enabled). Examples:

```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq
# Intake needs Bearer from POST /auth/login — see auth-supabase.md
# curl -s -X POST http://127.0.0.1:8000/api/v1/documents \
#   -H "Authorization: Bearer $TOKEN" -F "file=@./README.md" -F "title=Demo" | jq
```

SSE (Ctrl+C to stop):

```bash
curl -N -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/events/stream
```

## Default local URLs

| Service | URL |
|--------|-----|
| MinIO console | http://localhost:9001 |
| MinIO API | http://localhost:9000 |
| OpenSearch | http://localhost:9200 |
| OpenSearch Dashboards | http://localhost:5601 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |
| API (Compose `app`) | http://localhost:8000 |
