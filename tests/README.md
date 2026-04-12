# Tests

Pytest is organized by **markers** (see `pyproject.toml`):

| Marker | Scope | Requirements |
|--------|--------|----------------|
| **`unit`** | CLI, package metadata, migrations on disk, worker pipeline sim, event hub, document queue, **HTTP scorer parsing** (`test_score_http_remote.py`), **reference HTTP scorer** (`test_reference_http_scorer_app.py`), **SSE tenancy filter** (`test_sse_tenancy.py`) | None |
| **`integration`** | Postgres schema, **document intake** (`test_document_intake.py`), **search pipeline** (`test_search_pipeline.py`), **pipeline + analytics HTTP** (`test_pipeline_and_analytics_api.py`), **async HTTP scorer** (`test_score_http_worker.py`), **search/SSE auth defaults** (`test_auth_search_sse.py`), **collection CRUD** (`test_collection_mutations.py` — `intake_api_client` + optional `psycopg` seed for org membership), **document move/copy** (`test_document_collection_transfer.py`), or FastAPI routes (stubbed DB health + fake queue/storage/OpenSearch via `api_client`) | Intake + schema: **`DATABASE_URL`** + migrations **001–005**. `api_client` tests: none (fixture stubs infra). |
| **`e2e`** | `docker compose config` + ASGI smoke (`test_api_http`) | **`docker`** on `PATH` for compose test only |
| **`api`** | ASGI smoke (`TestClient`, multi-route) | None |

## Commands

```bash
make test                 # full pytest (skips only what markers/env exclude); no coverage gate
make test-unit
make test-integration
make test-e2e
make test-api
make ci-local             # like CI: Ruff + pytest with --cov=app/services (needs Docker)
```

## Integration tests and Postgres

Schema integration tests (`test_schema_*.py`) connect with **`psycopg`** using **`DATABASE_URL`**. They **do not** apply migrations; your pipeline (or you locally) must run the SQL in `db/migrations/` first (**001** through **005**).

**Intake** integration tests (`test_document_intake.py`) use the **`intake_api_client`** fixture: real Postgres, **`USE_FAKE_QUEUE=true`**, **`USE_FAKE_EVENT_HUB=true`**, **`USE_FAKE_STORAGE=true`** (in-memory S3 stand-in), full multipart **`POST /api/v1/documents`** flow.

**Identity / tenancy** integration and **e2e** tests use **`jwt_integration_client`** from **`tests/conftest.py`**: real Postgres, HS256 tokens, **no** `get_current_user` override, `SUPABASE_JWT_SECRET` set for the fixture. Skips when **`DATABASE_URL`** is unset.

API integration tests (`test_api_routes.py`) use the shared **`api_client`** fixture: fake queue, **`USE_FAKE_EVENT_HUB=true`** (in-process SSE hub), **fake storage**, patched DB health, **`resolve_accessible_collection_ids`** stubbed so **`GET /search`** does not need a live Postgres URL, and cleaned global state after each test.

**Redis SSE** (`test_sse_redis_pubsub.py`): optional integration test that publishes/subscribes with two **`RedisEventHub`** instances when **`REDIS_URL`** answers **`PING`**; skipped automatically when Redis is down.

## Integration tests and `api_client`

Defined in **`tests/conftest.py`**. Patches **`app.api.routes.health.database_health_check`** (Postgres) and **`check_opensearch_component`** so `/health` is **ok** without live Postgres or OpenSearch (patch names the route module uses).

## CI

GitHub Actions runs **`pytest`** on all markers with **`--cov=app/services`**, **`--cov-report=term-missing`**, and **`--cov-report=xml`**. Coverage enforces a **minimum line coverage** on **`app/services`** (**`fail_under`** in **`pyproject.toml`** `[tool.coverage.report]`). Ruff checks **`src`**, **`tests`**, **`app`**, **`worker`**, and **`scripts`**. The Python job runs **`pip-audit`** on an exported requirements file; the web job runs **`npm audit`**. The workflow uploads **`coverage.xml`** as an artifact when present. Locally, **`make ci-local`** approximates the same flow (see the root **`README.md`**).
