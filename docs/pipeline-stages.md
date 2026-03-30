# Document scaffold pipeline (worker)

The ARQ task **`process_document`** runs **`execute_scaffold_pipeline`** (`app/services/pipeline_run_service.py`), which advances **`pipeline_runs.stage`** and appends **`pipeline_events`** for observability.

## Stage order

Defined in **`app/pipeline/constants.py`** as **`DOCUMENT_SCAFFOLD_STAGES`**:

1. **`ingest`** — Verifies the raw object exists in storage (`object_exists` on **`documents.storage_key`**) without downloading the full body. Emits **`ingest_verified`**, **`ingest_skipped`**, or **`ingest_failed`**.
2. **`extract`** — **`get_bytes`** from storage, then **`extract_document_text`** (`app/services/document_content_extract.py`): **PDF** (`pypdf`), **DOCX** (`python-docx`), or the existing **plain / UTF-8 heuristic** path (`document_text_extract`). Truncated text is stored in **`documents.body_text`**; full extracted UTF-8 text is uploaded to **`artifacts/{document_id}/extracted.txt`** and **`documents.extract_artifact_key`** is set (migration **004**). Events: **`extract_complete`**, **`extract_failed`**, **`extract_skipped`**, **`extract_artifact_failed`** (upload error only).
3. **`enrich`** — Placeholder; emits **`enrich_complete`** with **`mode: noop`** until real enrichers exist.
4. **`score`** — If **`ENQUEUE_SCORE_AFTER_PIPELINE=true`**, enqueues **`score_document`** on Redis/ARQ (or records on the in-memory fake queue). Emits **`score_job_enqueued`**, **`score_skipped`**, or **`score_enqueue_failed`**. The **`score_document`** worker (`app/services/score_document_worker.py`) inserts a stub row into **`document_scores`** (`scorer_name`: **`verifiedsignal_stub`**) for wiring tests; replace with real scoring later.
5. **`index`** — Keyword index via **`index_document_sync`** (OpenSearch or fake). Events: **`index_complete`** / **`index_failed`**.
6. **`finalize`** — Stage marker only; run is completed and **`documents.status`** set to **`completed`**.

## Configuration

| Variable | Effect |
|----------|--------|
| **`ENQUEUE_SCORE_AFTER_PIPELINE`** | When **`true`**, the **`score`** stage enqueues **`score_document`** after extract/index prerequisites are done in the same run. Default **`false`**. |
| **`USE_FAKE_QUEUE`** | In-memory queue; **`score_document`** jobs are recorded but not executed unless you call the worker entrypoint yourself. |
| **`USE_FAKE_STORAGE`** | In-memory S3 stand-in; ingest/extract/artifact uploads use the same process-local dict. |
| **`USE_FAKE_OPENSEARCH`** | In-memory search index for tests. |

## Dependencies

- **`pypdf`** — PDF text extraction.
- **`python-docx`** — DOCX paragraph text.

## Migrations

**`documents.extract_artifact_key`** is added in **`db/migrations/004_document_extract_artifact.up.sql`**. Apply after **001–003** (see **`db/README.md`**).
