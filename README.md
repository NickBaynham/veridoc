# veridoc

A document intelligence platform. This repository uses **Python** with **[PDM](https://pdm-project.org/latest/)** for dependencies, a **Makefile** for setup and common tasks, and **Docker Compose** to run and test the app in containers.

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
   pdm run python -m veridoc
   ```

   Or, after install, use the console script:

   ```bash
   pdm run veridoc
   ```

4. Run tests and linters:

   ```bash
   make test
   make lint
   ```

## Makefile reference

Run `make` or `make help` to print this list from the Makefile.

| Target | Description |
|--------|-------------|
| `make setup` | Runs `make config`, then `pdm install` (requires `pdm` on `PATH`) |
| `make lock` | Regenerates `pdm.lock` from `pyproject.toml` |
| `make sync` / `make install` | Installs exactly what `pdm.lock` specifies |
| `make test` | `pdm run pytest` |
| `make lint` | `pdm run ruff check src tests` |
| `make format` | `pdm run ruff format src tests` |
| `make clean` | Removes common build and cache directories |
| `make config` | Copies `.env.example` → `.env` only if `.env` is missing |
| `make resources` | Placeholder for future asset or download steps |
| `make docker-build` | `docker compose build` |
| `make docker-up` | `make config`, then `docker compose up --build app` (foreground) |
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
pdm run pytest
pdm run ruff check src tests
pdm run ruff format src tests
```

Runtime dependencies live under `[project]` in `pyproject.toml`. Development tools (pytest, ruff, etc.) live in `[dependency-groups]` under `dev`.

## Docker Compose

The stack is defined in `docker-compose.yml`. **`make docker-up`** brings up every service below (except **`test`**, which is behind the `test` profile).

| Service | Role | Default host port |
|--------|------|-------------------|
| **postgres** | Canonical relational data (PostgreSQL 16) | `5432` |
| **redis** | Pub/sub, caching, worker coordination (Redis 7, AOF on) | `6379` |
| **minio** | S3-compatible object storage (API + web console) | `9000` (API), `9001` (console) |
| **opensearch** | Search and analytics (single-node; `DISABLE_SECURITY_PLUGIN=true` for local dev only) | `9200` |
| **opensearch-dashboards** | OpenSearch Dashboards UI | `5601` |
| **app** | veridoc application (`pdm run python -m veridoc`) | (none; attach logs via Compose) |
| **test** | Runs `pytest` in a one-off container (`profile: test`) | — |

The **app** service waits for **postgres**, **redis**, **minio**, and **opensearch** to pass their health checks before starting. Connection defaults are wired through environment variables (see **`.env.example`**); inside the Compose network the app receives URLs such as `postgresql://…@postgres:5432/…`, `redis://redis:6379/0`, `http://minio:9000`, and `http://opensearch:9200`.

**OpenSearch:** the cluster runs with the security plugin disabled via `DISABLE_SECURITY_PLUGIN=true` in Compose—suitable only for trusted local machines; do not expose these ports on a network. On **Linux**, if the node fails to start, raise `vm.max_map_count` (for example `sudo sysctl -w vm.max_map_count=262144`). See the [OpenSearch Docker install notes](https://opensearch.org/docs/latest/install-and-configure/install-opensearch/docker/).

**MinIO:** open `http://localhost:9001` and sign in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `.env` (defaults match the example file). Create a bucket named like `S3_BUCKET` (`veridoc` by default) when you begin storing objects.

Examples:

```bash
# Build the application image (infrastructure images are pulled as needed)
make docker-build

# Run the full stack in the foreground (rebuilds the app image if needed)
make docker-up

# Infrastructure only (no app container)
docker compose up -d postgres redis minio opensearch opensearch-dashboards

# Run tests in a throwaway container (profile `test`)
make docker-test

# One-off app run (starts dependencies if needed, then exits)
make docker-run

# Manual equivalents
docker compose up --build
docker compose --profile test run --rm test
docker compose run --rm app
```

`.env` is optional: **`app`** and **`test`** use `env_file` with `required: false`. Compose still applies defaults from `docker-compose.yml` when variables are unset. Run **`make config`** to create `.env` from **`.env.example`** so host port overrides and credentials stay consistent.

## Configuration and environment

- **`.env.example`** — template for local and Compose-related variables (Postgres, Redis, MinIO/S3, OpenSearch ports, `DATABASE_URL`, `REDIS_URL`, etc.). **`make config`** copies it to **`.env`** when `.env` is missing.
- **`VERIDOC_CONFIG_DIR`** — directory the CLI treats as the config root (default `config` if unset). Under Compose it is set to `/app/config` inside the container.
- **`config/`** — mount point for configuration files. **`config/application.example.yml`** is a sample; copy or adapt it for your own `application.yml` (or other files) as the product grows.

Do not commit secrets. `.env` is gitignored.

## Project layout

```
├── Makefile
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── pdm.lock
├── src/veridoc/       # application package
├── tests/             # pytest
└── config/            # runtime configuration (mounted in Docker)
```

## License

See [LICENSE](LICENSE).
