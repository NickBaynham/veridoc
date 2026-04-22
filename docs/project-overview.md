# Project overview

VerifiedSignal is a **document intelligence platform**: **PostgreSQL** is the system of record; **OpenSearch** is a derived, disposable index; **FastAPI** exposes HTTP + **SSE**; an **ARQ** worker runs async jobs on **Redis**. The repo uses **PDM**, a **Makefile**, **Docker Compose** for local infra, and a **React/Vite** app under `apps/web/`.

## What’s in the repository

- **CLI** — Python **3.11+**, `src/verifiedsignal/`, `pdm run verifiedsignal`.
- **Supabase session auth (optional)** — Routes under `/auth` (signup, login with httpOnly refresh cookie, refresh, logout, `POST /auth/sync-identity`). JWT via JWKS or HS256. Bearer requests can auto-provision Postgres users, personal org, and Inbox collection. See [auth-supabase.md](auth-supabase.md), [tenancy-postgres.md](tenancy-postgres.md), [accounts-and-collections.md](accounts-and-collections.md), [supabase/README.md](../supabase/README.md), [apps/web/README.md](../apps/web/README.md).
- **HTTP API** (`app/`) — FastAPI at `/api/v1`: health, document intake (`POST /documents`), keyword search (`GET /search`), collections, analytics, knowledge models ([model-writeback.md](model-writeback.md)), pipeline status, signed downloads, SSE (`/events/stream`). SQLAlchemy + Postgres; auth in `app/auth/`.
- **MCP server** (`mcp_server/`) — stdio MCP for tools like Claude Desktop. See [mcp-claude-desktop.md](mcp-claude-desktop.md); run `pdm run mcp-server`.
- **Worker** (`worker/`) — ARQ: ingest, extract, enrich, score, index, finalize; optional async HTTP scoring ([scoring-http.md](scoring-http.md), [external-scorer-implementation-guide.md](external-scorer-implementation-guide.md)). Knowledge model builds. See [pipeline-stages.md](pipeline-stages.md).
- **Web UI** — Dashboard, documents, upload (including local folder sync on `/library/upload`), search, collection workspace, knowledge models, analytics. `VITE_API_URL` enables API mode; unset uses mock demo.
- **PDM** — `pyproject.toml`, `pdm.lock`; scripts: `pdm run api`, `api-prod`, `worker`, `reference-http-scorer`.
- **Makefile** — `setup`, tests, `ci-local`, lint, Docker helpers, `dev` / `web-dev`. See [commands.md](commands.md).
- **Tests** — Pytest markers: `unit`, `integration`, `e2e`, `api`. See [tests/README.md](../tests/README.md). CI currently runs `-m "not integration"` (run integration locally with `DATABASE_URL` + migrations).
- **CI** — [.github/workflows/ci.yml](../.github/workflows/ci.yml): Ruff, pip-audit, pytest + coverage (`app/services`, floor in `pyproject.toml`), web build + Playwright. [dependabot.yml](../.github/dependabot.yml) for Actions, pip, npm.
- **Docker** — `Dockerfile`, `docker-compose.yml`: Postgres, Redis, MinIO, OpenSearch, app, worker, optional web/scoring. See [docker-compose.md](docker-compose.md).
- **Database** — SQL migrations in `db/migrations/`. See [db/README.md](../db/README.md).
- **Design notes** — [document-metadata-design.md](document-metadata-design.md) (metadata, tags, OpenSearch). [end-user/README.md](end-user/README.md) for product-oriented guides.

## End-user and operator docs

- [end-user/README.md](end-user/README.md) — Getting started, signing in, documents, search/events, workspace, troubleshooting.
- [url-ingest.md](url-ingest.md) — URL intake and SSRF notes.
- [end-user/search-and-events.md](end-user/search-and-events.md) — Search + SSE auth defaults.
