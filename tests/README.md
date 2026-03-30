# Tests

Pytest is organized by **markers** (see `pyproject.toml`):

| Marker | Scope | Requirements |
|--------|--------|----------------|
| **`unit`** | CLI, package metadata, migrations on disk, worker pipeline sim, event hub, document queue | None |
| **`integration`** | Postgres schema, **document intake** (`test_document_intake.py`), **search pipeline** (`test_search_pipeline.py`), or FastAPI routes (stubbed DB health + fake queue/storage/OpenSearch via `api_client`) | Intake + schema: **`DATABASE_URL`** + migrations **001–004**. `api_client` tests: none (fixture stubs infra). |
| **`e2e`** | `docker compose config` + ASGI smoke (`test_api_http`) | **`docker`** on `PATH` for compose test only |
| **`api`** | ASGI smoke (`TestClient`, multi-route) | None |

## Commands

```bash
make test                 # full pytest (skips only what markers/env exclude)
make test-unit
make test-integration
make test-e2e
make test-api
```

## Integration tests and Postgres

Schema integration tests (`test_schema_*.py`) connect with **`psycopg`** using **`DATABASE_URL`**. They **do not** apply migrations; your pipeline (or you locally) must run the SQL in `db/migrations/` first (**001** through **004**).

**Intake** integration tests (`test_document_intake.py`) use the **`intake_api_client`** fixture: real Postgres, **`USE_FAKE_QUEUE=true`**, **`USE_FAKE_STORAGE=true`** (in-memory S3 stand-in), full multipart **`POST /api/v1/documents`** flow.

**Identity / tenancy** integration and **e2e** tests use **`jwt_integration_client`** from **`tests/conftest.py`**: real Postgres, HS256 tokens, **no** `get_current_user` override, `SUPABASE_JWT_SECRET` set for the fixture. Skips when **`DATABASE_URL`** is unset.

API integration tests (`test_api_routes.py`) use the shared **`api_client`** fixture: fake queue, **fake storage**, patched DB health, and cleaned global state after each test.

## Integration tests and `api_client`

Defined in **`tests/conftest.py`**. Patches **`app.api.routes.health.database_health_check`** (Postgres) and **`check_opensearch_component`** so `/health` is **ok** without live Postgres or OpenSearch (patch names the route module uses).

## CI

GitHub Actions runs **`pdm run python -m pytest`** (all markers) plus Ruff on **`src`**, **`tests`**, **`app`**, and **`worker`**. Locally, **`make ci-local`** approximates that flow (see the root **`README.md`**).
