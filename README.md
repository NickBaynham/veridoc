# VerifiedSignal

A **document intelligence platform**: ingest documents, run a pipeline (extract, score, index), search with OpenSearch, and expose a FastAPI API plus a React dashboard. **PostgreSQL** is the source of truth; **OpenSearch** is disposable; **Redis** + **ARQ** handle background work.

This repo uses **[PDM](https://pdm-project.org/latest/)** for Python, a **Makefile** for workflows, and **Docker Compose** for local infrastructure.

**Documentation:** start at **[docs/README.md](docs/README.md)** — especially [Project overview](docs/project-overview.md), [Developing locally](docs/developing-locally.md), and [Commands](docs/commands.md).

## Prerequisites

- Python **3.11+**
- **[PDM](https://pdm-project.org/latest/#installation)**
- **GNU Make**
- **Docker** + **Docker Compose** v2 (for the recommended local stack)

## Quick start

```bash
git clone <repository-url> && cd verifiedsignal
make setup
pdm run python -m verifiedsignal   # CLI smoke
make test && make lint
```

**Day-to-day API + infra:** `make dev` (Compose services + FastAPI with reload). First time: `make migrate`. **Web UI:** `make web-dev` (set `VITE_API_URL` in `apps/web` — see [apps/web/README.md](apps/web/README.md)).

Details: **[docs/developing-locally.md](docs/developing-locally.md)**.

## Security & audits

Staging/production hardening and how to run **pip-audit** / **npm audit** locally: **[docs/security.md](docs/security.md)**.

## Configuration

- **`.env.example`** → copy to `.env` (`make config` if missing): DB, Redis, S3, OpenSearch, auth, feature flags.
- **`config/`** — optional YAML (e.g. `application.example.yml`); `VERIFIEDSIGNAL_CONFIG_DIR` overrides root (default `config`).
- **Migrations:** `db/migrations/*.up.sql` — apply with `make migrate` or `psql`; see **[db/README.md](db/README.md)**.

Do not commit secrets; `.env` is gitignored.

## Project layout

```
├── Makefile                 # dev, test, docker helpers
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml / pdm.lock
├── .github/workflows/     # CI
├── app/                     # FastAPI
├── worker/                  # ARQ worker
├── mcp_server/              # MCP (Claude Desktop, etc.)
├── apps/web/                # React / Vite SPA
├── db/migrations/           # SQL schema
├── src/verifiedsignal/      # CLI package
├── tests/                   # pytest — see tests/README.md
├── docs/                    # guides (see docs/README.md)
└── config/                  # runtime config samples
```

## License

See [LICENSE](LICENSE).

2026, CalgentiK
