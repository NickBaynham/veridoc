# VerifiedSignal database (PostgreSQL)

This directory holds **canonical** schema definitions for VerifiedSignal. The application treats **PostgreSQL as the write master and system-of-record**. OpenSearch (or Elasticsearch) is a **derived search layer** only.

## Migrations

| File | Purpose |
|------|---------|
| `migrations/001_initial_schema.up.sql` | Creates core tables, indexes, constraints, and the shared `updated_at` trigger. |
| `migrations/001_initial_schema.down.sql` | Drops those objects (destructive). |
| `migrations/002_intake_document_fields.up.sql` | Intake columns on **`documents`**, expanded **`documents.status`** check, **`document_sources`**-ready lifecycle; seeds **`local-dev`** org and **`default-inbox`** collection for local UUIDs. |
| `migrations/002_intake_document_fields.down.sql` | Rollback (destructive; removes seeded rows by id/slug). |
| `migrations/003_document_body_text.up.sql` | Adds **`documents.body_text`** for extracted plain text (keyword search path). |
| `migrations/003_document_body_text.down.sql` | Drops **`body_text`**. |
| `migrations/004_document_extract_artifact.up.sql` | Adds **`documents.extract_artifact_key`** (object key for full extracted UTF-8 text). |
| `migrations/004_document_extract_artifact.down.sql` | Drops **`extract_artifact_key`**. |
| `migrations/005_documents_user_metadata.up.sql` | Adds **`documents.user_metadata`** JSONB (client intake metadata; GIN index). |
| `migrations/005_documents_user_metadata.down.sql` | Drops **`user_metadata`**. |
| `migrations/006_knowledge_models.up.sql` | **Knowledge models**: `knowledge_models`, `knowledge_model_versions`, `knowledge_model_assets`, `model_build_runs` (versioned, auditable builds from selected collection documents). |
| `migrations/006_knowledge_models.down.sql` | Rollback (drops knowledge-model tables). |
| `migrations/007_model_writebacks.up.sql` | **Model write-back**: `model_writeback_artifacts`, `model_writeback_events` (findings, risks, tests, execution, evidence, contradictions; provenance + verification). |
| `migrations/007_model_writebacks.down.sql` | Rollback (drops write-back tables). |
| `migrations/008_document_analysis_metadata.up.sql` | **`documents.analysis_metadata`** JSONB + **`document_tags`** (normalized tags with source + optional confidence). |
| `migrations/008_document_analysis_metadata.down.sql` | Rollback (drops tags table + column). |

Design reference for metadata layers: **[`docs/document-metadata-design.md`](../docs/document-metadata-design.md)**. **`user_metadata`** is in **005**; **008** adds worker **`analysis_metadata`** and **`document_tags`**.

### Applying manually

From the repo root, with **Docker Compose Postgres** already running (`docker compose up -d postgres`):

```bash
make migrate
```

That applies **001** through **007** via `docker compose exec` (same as below).

**`relation "users" already exists`:** **001** is already applied. You may only need **002**–**007**:

```bash
make migrate-002
# or, when 001+002 are applied but body_text is missing:
make migrate-003
# or, when 001–003 are applied but extract_artifact_key is missing:
make migrate-004
# or, when 001–004 are applied but user_metadata is missing:
make migrate-005
# or, when 001–005 are applied but knowledge models are missing:
make migrate-006
```

or the database is fully migrated already and you can ignore the error. To wipe dev data and re-run migrations:

```bash
make migrate-reset MIGRATE_RESET_OK=1
```

With Docker Compose Postgres (from the repo root):

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/001_initial_schema.up.sql
docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/002_intake_document_fields.up.sql
docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/003_document_body_text.up.sql
docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/004_document_extract_artifact.up.sql
docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/005_documents_user_metadata.up.sql
docker compose exec -T postgres psql -U verifiedsignal -d verifiedsignal -v ON_ERROR_STOP=1 < db/migrations/006_knowledge_models.up.sql
```

Or from a host with `psql`:

```bash
psql "postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal" -v ON_ERROR_STOP=1 -f db/migrations/001_initial_schema.up.sql
psql "postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal" -v ON_ERROR_STOP=1 -f db/migrations/002_intake_document_fields.up.sql
psql "postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal" -v ON_ERROR_STOP=1 -f db/migrations/003_document_body_text.up.sql
psql "postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal" -v ON_ERROR_STOP=1 -f db/migrations/004_document_extract_artifact.up.sql
psql "postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal" -v ON_ERROR_STOP=1 -f db/migrations/005_documents_user_metadata.up.sql
psql "postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal" -v ON_ERROR_STOP=1 -f db/migrations/006_knowledge_models.up.sql
```

Rollback (destructive):

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/001_initial_schema.down.sql
```

Use a migration runner (Flyway, Sqitch, Alembic raw SQL, etc.) in production; these files are the **source of truth** for the DDL.

After migrations are applied, **`pytest -m integration`** (see [`tests/README.md`](../tests/README.md)) validates tables and constraints against **`DATABASE_URL`**.

## Schema overview

### Entities

- **users** — Actors in the system; **organization_members** links users to **organizations** with a role (`owner`, `admin`, `member`, `viewer`).
- **organizations** — Tenant boundary; owns **collections**.
- **collections** — Groups **documents** under an org (`UNIQUE (organization_id, slug)`).
- **documents** — Logical documents; **`body_text`** holds extracted plain text (truncated) for keyword search; **`extract_artifact_key`** points at full extracted UTF-8 in object storage; **`user_metadata`** JSONB for client tags/labels (indexed for search); OpenSearch document id = `documents.id` for reindex.
- **document_sources** — Many sources per document (URL, upload, API, etc.) with `raw_metadata` JSONB.
- **pipeline_runs** — One pipeline execution per document (name/version, `status`, `stage`, timing, errors).
- **pipeline_events** — Append-style log lines per run (`step_index` + `event_type` + `payload` JSONB).
- **document_scores** — Time series of scores per document; **at most one** `is_canonical = true` row per document (partial unique index). Promoted numeric columns (`factuality_score`, `ai_generation_probability`, `fallacy_score`, `confidence_score`) are all on **[0, 1]** when present; **`score_payload`** JSONB holds extra model output.

### Design choices

- **UUID primary keys** — Safe generation across services; stable public identifiers for sync to search.
- **TEXT + CHECK** for statuses/stages — Adding a new value is a small, explicit migration without enum type surgery.
- **`created_at` / `updated_at`** — Auditing and incremental export windows; trigger keeps `updated_at` consistent.
- **JSONB** — `organizations.metadata`, `document_sources.raw_metadata`, `run_metadata`, `error_detail`, `payload`, `score_payload` for evolution without wide nullable columns for every new field. Planned document-level metadata is specified in **[`docs/document-metadata-design.md`](../docs/document-metadata-design.md)**.
- **`score_schema_version` / `row_schema_version` / `definition_schema_version`** — Lets application code branch on row semantics during rolling upgrades.

### Why Postgres is canonical

All durable business facts—who owns what, document identity, provenance, pipeline outcomes, and scoring history—live here with **ACID transactions** and **referential integrity**. If OpenSearch diverges or is wiped, you can **rebuild the index** by reading documents (plus denormalized fields you choose to project, e.g. canonical scores) and re-running indexing logic.

### Why the search index is disposable

OpenSearch holds **inverted indices and denormalized projections** for search relevance and aggregations. None of that is authoritative: it can drift, lag, or be corrupted without losing truth, as long as **Postgres + pipeline history** remain intact. Reindex = batch or stream from Postgres (and optionally replay pipeline semantics), not the other way around.

### How this supports reindexing and pipeline auditing

- **Reindexing:** `documents` keyed by UUID; `collections` / `organizations` provide stable partition keys. Join to **`document_scores`** where `is_canonical` to project current metrics into the index. Full rebuild = scan or cursor over `documents` (filtered by collection/org) and bulk index.
- **Pipeline auditing:** **`pipeline_runs`** record attempts and outcomes per document; **`pipeline_events`** capture ordered steps and structured **`payload`**, independent of search. Debugging a bad index row traces back to a specific **run** and **event** trail in Postgres.

### Canonical scores

Only one row per `document_id` may have `is_canonical = true`. When promoting a new score, do it in **one transaction**: set existing canonical rows to `false`, then insert or update the new canonical row. The partial unique index enforces integrity at the database level.
