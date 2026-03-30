# URL-based document intake

**End-user how-to:** [`end-user/documents.md#submitting-a-document-by-url`](end-user/documents.md#submitting-a-document-by-url) — this page is the **technical** reference (worker, SSRF, env vars).

Submit a **remote HTTPS (or HTTP in dev) URL** instead of uploading bytes through the browser. The flow matches **multipart file intake** after bytes are stored: same **`raw/{document_id}/…`** object key, **`document_sources`** `upload` row, and **`process_document`** ARQ job.

## API

`POST /api/v1/documents/from-url`  
**Auth:** `Authorization: Bearer <access_token>` (same as other `/documents` routes)

**Status:** **202 Accepted**

**JSON body:**

| Field | Required | Description |
|--------|----------|-------------|
| `url` | yes | Max 8192 chars; `https:` preferred |
| `collection_id` | no | UUID string; defaults to `VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID` |
| `title` | no | Display title; defaults from URL path segment |

**Response:**

```json
{
  "document_id": "uuid",
  "status": "created",
  "source_url": "https://example.com/normalized-path",
  "job_id": "…",
  "enqueue_error": null
}
```

- **`status: "created"`** means the row exists and a **`fetch_url_and_ingest`** job was enqueued (or `enqueue_error` is set if enqueue failed).
- After the worker runs: document moves to **`queued`** (storage + `upload` source), then **`process_document`** runs (pipeline). Poll **`GET /api/v1/documents/{id}`** for `status`, `storage_key`, and `ingest_error` / `enqueue_error`.

## Worker jobs

| Job | Role |
|-----|------|
| `fetch_url_and_ingest` | HTTP GET (streamed, size-capped) → S3/MinIO → `finalize_intake_after_upload` → enqueue `process_document` |
| `process_document` | Unchanged scaffold pipeline (`pipeline_runs` / `documents.status`) |

Both must be registered on the ARQ worker (`worker.main.WorkerSettings.functions`).

## Security (SSRF)

Before any row is written, the API:

- Allows only **`http`** / **`https`** (`http` requires **`ALLOW_HTTP_URL_INGEST=true`**).
- Rejects URLs with **embedded credentials** (`user:pass@host`).
- If **`URL_FETCH_BLOCK_PRIVATE_NETWORKS`** is true (default): rejects **literal** private/link-local/loopback IPs and rejects hostnames that **resolve** to any disallowed address.

**Redirects:** When **`URL_FETCH_FOLLOW_REDIRECTS`** is true, httpx follows up to **`URL_FETCH_MAX_REDIRECTS`**. Only the **initial** hostname is resolved for the SSRF check; each redirect hop is **not** re-validated (documented limitation—use an egress proxy or disable redirects for stricter deployments).

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `URL_INGEST_ENABLED` | `true` | Master switch |
| `URL_FETCH_MAX_BYTES` | same as `MAX_UPLOAD_BYTES` | Max response body |
| `URL_FETCH_TIMEOUT_S` | `60` | Total request timeout |
| `URL_FETCH_MAX_REDIRECTS` | `5` | Redirect cap |
| `URL_FETCH_FOLLOW_REDIRECTS` | `true` | Follow 3xx |
| `ALLOW_HTTP_URL_INGEST` | `false` | Allow `http://` URLs |
| `URL_FETCH_BLOCK_PRIVATE_NETWORKS` | `true` | Block RFC private/reserved targets |

See **`.env.example`** for copy-paste entries.

## Data model

- On submit: **`documents`** row **`created`**, **`file_size`** null, **`document_sources`** row with **`source_kind: url`** and **`locator`** = normalized URL.
- After fetch: **`upload`** source row (`s3://…`), **`storage_key`** set, **`status: queued`**, then pipeline as for multipart uploads.

## Tests

- **Unit:** `tests/unit/test_url_ingest_ssrf.py`, `tests/unit/test_intake_queue_and_resolve.py` (enqueue shape).
- **Integration:** `tests/integration/test_url_ingest.py` (requires Postgres + migrations; uses mocked HTTP fetch for worker steps).

Run **`make ci-local`** for the full suite including integration tests.
