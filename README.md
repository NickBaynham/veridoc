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

The stack is defined in `docker-compose.yml`.

- **`app`** — builds the image, mounts `./config` at `/app/config` read-only, sets `VERIDOC_CONFIG_DIR=/app/config`, and runs `pdm run python -m veridoc`.
- **`test`** — same image and mounts; runs `pdm run pytest`. It uses Compose **profile** `test`, so it is not started by a plain `docker compose up` unless you enable that profile.

Examples:

```bash
# Build images
make docker-build

# Run the app in the foreground (rebuilds if needed)
make docker-up

# Run tests in a throwaway container (uses profile `test`)
make docker-test

# One-off app run (exits after the command)
make docker-run

# Equivalent manual invocations
docker compose up --build app
docker compose --profile test run --rm test
docker compose run --rm app
```

`.env` is optional at runtime: both services declare `env_file` with `required: false`, so Compose works before you run `make config`. Values in `docker-compose.yml` (for example `VERIDOC_CONFIG_DIR` for containers) still apply.

## Configuration and environment

- **`.env.example`** — template for local and Compose-related variables. **`make config`** copies it to **`.env`** when `.env` is missing.
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
