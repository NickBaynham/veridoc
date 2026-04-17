# Document scaffold pipeline (worker)

The ARQ task **`process_document`** runs **`execute_scaffold_pipeline`** (`app/services/pipeline_run_service.py`), which advances **`pipeline_runs.stage`** and appends **`pipeline_events`** for observability.

## Stage order

Defined in **`app/pipeline/constants.py`** as **`DOCUMENT_SCAFFOLD_STAGES`**:

1. **`ingest`** — Verifies the raw object exists in storage (`object_exists` on **`documents.storage_key`**) without downloading the full body. Emits **`ingest_verified`**, **`ingest_skipped`**, or **`ingest_failed`**.
2. **`extract`** — **`get_bytes`** from storage, then **`extract_document_text`** (`app/services/document_content_extract.py`): **PDF** (`pypdf`), optional **scanned-PDF OCR** when native text is empty (**`pdf2image`** + **Tesseract**; see **`OCR_*`** env vars), **DOCX** (`python-docx`), **images** (**`image/*`** and common raster suffixes) via **Tesseract** when **`OCR_ENABLED`**, or the **plain / UTF-8 heuristic** path (`document_text_extract`). Truncated text is stored in **`documents.body_text`**; full extracted UTF-8 text is uploaded to **`artifacts/{document_id}/extracted.txt`** and **`documents.extract_artifact_key`** is set (migration **004**). Events: **`extract_complete`**, **`extract_failed`**, **`extract_skipped`**, **`extract_artifact_failed`** (upload error only).
3. **`enrich`** — Lightweight **text stats** on **`documents.body_text`**: word/character counts and **`has_body_text`** in the **`enrich_complete`** payload (`mode`: **`text_stats`**). Swap in real enrichers (NER, embeddings, etc.) behind the same stage name when ready.
4. **`score`** — Always writes a **canonical** heuristic row via **`verifiedsignal_heuristic`** (`app/services/heuristic_score.py`): **`factuality_score`** and **`ai_generation_probability`** are deterministic proxies from lexical diversity (not ML). If **`ENQUEUE_SCORE_AFTER_PIPELINE=true`**, also enqueues **`score_document`** on Redis/ARQ. Emits **`score_job_enqueued`**, **`score_skipped`**, or **`score_enqueue_failed`**. The **`score_document`** worker (`app/services/score_document_worker.py`) adds a **second** row: **`SCORE_ASYNC_BACKEND=stub`** → non-canonical **`verifiedsignal_stub`**; **`SCORE_ASYNC_BACKEND=http`** → **`verifiedsignal_http`** via **`POST`** to **`SCORE_HTTP_URL`** (see **[`docs/scoring-http.md`](scoring-http.md)**). Optional **`SCORE_API_PROMOTE_CANONICAL=true`** makes the HTTP row canonical and demotes others. The ARQ task retries transient HTTP failures (**`max_tries=5`**).
5. **`index`** — Keyword index via **`index_document_sync`** (OpenSearch or fake). Events: **`index_complete`** / **`index_failed`**.
6. **`finalize`** — Stage marker only; run is completed and **`documents.status`** set to **`completed`**.

## Configuration

| Variable | Effect |
|----------|--------|
| **`ENQUEUE_SCORE_AFTER_PIPELINE`** | When **`true`**, the **`score`** stage enqueues **`score_document`** after extract/index prerequisites are done in the same run. Default **`false`**. |
| **`SCORE_ASYNC_BACKEND`** | **`stub`** (default) or **`http`** for the async scoring job. |
| **`SCORE_HTTP_URL`** / **`SCORE_HTTP_BEARER_TOKEN`** / **`SCORE_HTTP_TIMEOUT_S`** / **`SCORE_HTTP_MAX_BODY_CHARS`** / **`SCORE_HTTP_SCORER_VERSION`** | Remote HTTP scorer (see **`docs/scoring-http.md`**). |
| **`SCORE_API_PROMOTE_CANONICAL`** | When **`true`**, successful HTTP score replaces canonical heuristic for API/UI. |
| **`USE_FAKE_QUEUE`** | In-memory queue; **`score_document`** jobs are recorded but not executed unless you call the worker entrypoint yourself. |
| **`USE_FAKE_STORAGE`** | In-memory S3 stand-in; ingest/extract/artifact uploads use the same process-local dict. |
| **`USE_FAKE_OPENSEARCH`** | In-memory search index for tests. |

## Dependencies

- **`pypdf`** — PDF text extraction.
- **`python-docx`** — DOCX paragraph text.
- **`Pillow`** / **`pytesseract`** — raster OCR (images; also used after PDF render).
- **`pdf2image`** — PDF page rasterization (requires **Poppler** `pdftoppm` on the worker host).
- **Tesseract** — `tesseract` binary on **`PATH`** (or **`TESSERACT_CMD`**). The app **Dockerfile** installs **`tesseract-ocr`** and **`poppler-utils`**.

## Migrations

**`documents.extract_artifact_key`** is added in **`db/migrations/004_document_extract_artifact.up.sql`**. Apply after **001–003** (see **`db/README.md`**).

## Tests

- **Unit:** `tests/unit/test_document_content_extract.py` (routing + extract), `tests/unit/test_intake_storage.py` (artifact key / `object_exists`), `tests/unit/test_queue_score_enqueue.py`, `tests/unit/test_heuristic_score.py`, `tests/unit/test_facet_aggregation_sync.py`.
- **Integration:** `tests/integration/test_collections_and_pipeline.py` — plain text, **PDF** and **DOCX** intake → **`execute_scaffold_pipeline`** → **`body_text`**, **`extract_artifact_key`**, and in-memory storage artifact bytes; optional score enqueue and stub **`document_scores`** row. **`tests/integration/test_score_http_worker.py`** — HTTP scorer path (mocked transport), idempotency, canonical promotion.
