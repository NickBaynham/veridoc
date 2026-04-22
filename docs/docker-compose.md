# Docker Compose

Stack: [docker-compose.yml](../docker-compose.yml). `make docker-up` runs everything except the `test` profile by default.

## Scoring service (optional)

The **scoring-service** image builds from sibling **`../scoring-service`** (override `SCORING_SERVICE_REPO` in `.env`). Set `OPENAI_API_KEY` for real LLM scores. Worker defaults: `SCORE_HTTP_URL=http://scoring-service:8000/v1/score` and bearer token aligned with scoring-service config.

## Services

| Service | Role | Default host port |
|--------|------|-------------------|
| postgres | PostgreSQL 16 | 5432 |
| redis | Pub/sub, ARQ | 6379 |
| minio | S3-compatible | 9000 / 9001 console |
| opensearch | Search index | 9200 |
| opensearch-dashboards | UI | 5601 |
| scoring-postgres | DB for scoring-service only | internal |
| scoring-service | LLM scorer API | 8010 → `SCORING_SERVICE_PORT` |
| app | FastAPI | 8000 → `API_PORT` |
| worker | ARQ | — |
| web | Static React (nginx) | 5173 → `WEB_PORT` |
| test | One-off pytest (`profile: test`) | — |

**app** waits on postgres + redis. Env follows `.env.example`. OpenSearch in Compose uses `DISABLE_SECURITY_PLUGIN=true` — **local dev only**; do not expose on a network. On Linux, if OpenSearch fails to start, raise `vm.max_map_count` (e.g. `sudo sysctl -w vm.max_map_count=262144`) — [OpenSearch Docker docs](https://opensearch.org/docs/latest/install-and-configure/install-opensearch/docker/).

**MinIO:** http://localhost:9001 — create a bucket matching `S3_BUCKET` (default `verifiedsignal`).

`.env` is optional for Compose (`required: false`); `make config` seeds it from `.env.example`.

## Web UI with Docker API

**A — Static UI in Compose:** `web` at http://127.0.0.1:5173 (`WEB_PORT`). Rebuild after UI changes: `docker compose up -d --build web`. If API is not on 8000, set `WEB_VITE_API_URL`.

**B — Vite on host:** `apps/web` with `VITE_API_URL=http://127.0.0.1:8000` (`make web-config`). Use `127.0.0.1` consistently for CORS/cookies. For Supabase, see [supabase/README.md](../supabase/README.md). API in Docker rewrites loopback to `host.docker.internal` for `SUPABASE_URL` when needed.

Apply migrations on fresh volumes: `make migrate` (or per-file from [db/README.md](../db/README.md)).

## Makefile targets (Docker)

| Target | Description |
|--------|-------------|
| `make docker-build` | `docker compose build` |
| `make docker-up` | `make config` + `docker compose up --build` |
| `make docker-down` | `docker compose down` |
| `make docker-test` | Build + `docker compose --profile test run --rm test` |
| `make docker-run` | One-off `app` container |
