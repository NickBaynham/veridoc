# Design: document metadata extraction, storage, and enrichment

This document specifies how VerifiedSignal should **capture**, **persist**, and **refine** metadata that travels with a document—from client-supplied fields and source-derived hints through **pipeline analysis and tagging**. It is aligned with the current stack (**PostgreSQL** as source of truth, **`document_sources`**, **ARQ worker**, scaffold **pipeline stages**, future **OpenSearch**).

---

## 1. Goals

| Goal | Description |
|------|-------------|
| **Carry-in metadata** | Accept structured metadata at intake (upload, URL, future API) without losing fidelity. |
| **Source metadata** | Record protocol- and origin-specific fields (HTTP headers, filename, CMS ids, email headers) tied to **provenance**, not only to the logical document row. |
| **Extracted facts** | Persist outputs of **extract**-class steps (text stats, detected language, embedded dates, entities-as-JSON, etc.) with clear provenance. |
| **Enriched / inferred** | Persist **enrich** / **score** / **tagging** outputs separately from user and extract layers so conflicts and audits are understandable. |
| **Tags** | Support **normalized tags** for filtering and search (facets), with optional **confidence** and **source** (user vs model vs rule). |
| **Evolvability** | Add new fields without wide nullable columns everywhere; keep a path to **re-run** enrichment without destroying user overrides. |

### Non-goals (for this design)

- Choosing specific ML models or OCR engines.
- Full ontology / taxonomy management UI (only **tag strings** and optional **namespace**).
- Replacing **`document_scores`** promoted columns; those remain the place for **canonical scalar scores** when you promote them.

---

## 2. Current state (baseline)

- **`documents`**: `title`, `external_key`, `content_type`, `file_size`, `storage_key`, lifecycle **`status`**, etc.
- **`document_sources`**: `raw_metadata` **JSONB** (already the right place for **per-source** blobs at ingest).
- **`pipeline_runs` / `pipeline_events`**: append-only **audit** of stages; **`payload` JSONB** can hold step outputs but is **not** a substitute for queryable document metadata.
- **Pipeline stages** (scaffold): `ingest` → `extract` → `enrich` → `score` → `index` → `finalize`.

**Gap:** there is no first-class, queryable place for **merged “current” metadata** or **tags** that APIs and OpenSearch can consume without scraping all pipeline events.

---

## 3. Conceptual layers

Think of metadata in **four layers** (plus tags as a first-class slice):

| Layer | Origin | Typical content | Mutability |
|-------|--------|-----------------|------------|
| **User** | Client / integration | Title override, department, case id, custom key-value | User/API until policy locks it |
| **Source** | Ingest + transport | URL, `Content-Type`, filename, redirect chain, email `Message-Id` | Append/update at ingest; immutable after “sealed” ingest optional |
| **Extracted** | **extract** stage | Language, page count, detected headings, tables summary JSON | Overwritten on **re-extract** of same version |
| **Enriched** | **enrich** / **score** / **tagging** | Topics, risk flags, summarization snippets, model version ids | Overwritten on re-run; keep **history** via pipeline_events or optional **snapshots** |

**Tags** are either:

- **Structured rows** (recommended for filters): `document_tags` table, **normalized** string + **source** + optional **confidence** + link to **`pipeline_run_id`**, or  
- **Denormalized arrays** inside JSONB (convenient for OpenSearch bulk export) — **derived** from the table or merged at index time.

**Rule of thumb:** **Postgres = normalized tags + JSONB blobs for rich shapes**; **OpenSearch = denormalized projection** for search.

---

## 4. Recommended storage (hybrid)

### 4.1 `documents.user_metadata` (JSONB)

- **Default** `{}`.
- Written at **intake** from optional client payload (multipart field or JSON body for URL/API).
- **Schema:** convention-based keys, e.g. `custom`, `integration`, `labels` — document in OpenAPI; optional **JSON Schema** per collection later.
- **ACL:** readable with document; writable via **PATCH** (new route) with same rules as document update (future).

### 4.2 `documents.analysis_metadata` (JSONB)

- **Default** `{}`.
- **Structured interior** by **stage** or **namespace** to avoid silent overwrites, e.g.:

```json
{
  "extract": {
    "schema_version": 1,
    "language": "en",
    "page_count": 12,
    "entities": []
  },
  "enrich": {
    "schema_version": 1,
    "summary": "...",
    "topics": ["contracts", "nda"]
  },
  "tagging": {
    "schema_version": 1,
    "suggested": ["legal", "high_value"]
  }
}
```

- **Writers:** worker pipeline steps only (service role), not end-user JWTs (unless you add an explicit “admin enrich” API).
- **Merge policy:** each top-level key (`extract`, `enrich`, …) is **replaced wholesale** when that stage completes successfully; partial deep-merge per field is **phase 2** (see §10).

### 4.3 `document_sources.raw_metadata` (existing)

- Continue storing **transport/source** facts here (HTTP headers subset, upload form extras, URL canonicalization notes).
- On **finalize** of ingest, optionally **copy a normalized subset** into `analysis_metadata.ingest` **or** only into `user_metadata` if the client provided it—avoid duplicating large blobs in three places; **link** by `document_sources.id` in extracted JSON if needed.

### 4.4 `document_tags` (new table)

Normalized tags for **SQL filters** and **unique constraints**.

| Column | Purpose |
|--------|---------|
| `id` | UUID PK |
| `document_id` | FK → `documents` |
| `tag` | Display / original string |
| `tag_normalized` | `lower(trim(tag))` for matching (CHECK or app-enforced) |
| `source` | `user` \| `pipeline` \| `rule` \| `import` |
| `pipeline_run_id` | Nullable FK → `pipeline_runs` |
| `confidence` | Nullable `NUMERIC(6,5)` in [0, 1] |
| `created_at` | timestamptz |

**Unique:** `(document_id, tag_normalized, source)` — same tag from user and pipeline can both exist (intentional).

**Indexes:** `(tag_normalized)`, `(document_id)`.

**Sync with JSONB:** pipeline may write **`analysis_metadata.tagging.suggested`** and **insert rows** into `document_tags` for anything above a confidence threshold; or **only** insert rows and derive arrays at index time.

### 4.5 Optional later: `document_metadata_entries` (EAV)

If you need **many** typed facts with **per-key** ACL or **frequent** ad hoc keys:

- `(document_id, namespace, key)` unique, `value JSONB`, `pipeline_run_id`, `confidence`.
- **Heavier** to query without careful indexing; use when JSONB blobs become unwieldy.

---

## 5. Provenance and confidence

- **Pipeline:** every automated write should record **`pipeline_run_id`** on **`document_tags`** and optionally embed `"run_id"` inside the relevant **`analysis_metadata`** subtree.
- **Confidence:** store on **tags** and optionally inside **enrich** JSON for individual fields (`{"value": "...", "confidence": 0.82}`).
- **Audit:** keep **`pipeline_events`** payloads with **full model raw output** for debugging; **`analysis_metadata`** holds **curated** subsets for the product API.

---

## 6. Pipeline integration

| Stage | Responsibility |
|-------|----------------|
| **ingest** | Fill **`document_sources.raw_metadata`**; optionally seed **`analysis_metadata.ingest`** summary; map HTTP/URL headers into **source** layer. |
| **extract** | Write **`analysis_metadata.extract`**; idempotent replace for `extract` key. |
| **enrich** | Write **`analysis_metadata.enrich`**; add/update **`document_tags`** (`source='pipeline'`) when producing labels. |
| **score** | Continue using **`document_scores`** for promoted metrics; optional pointer in **`analysis_metadata.score`** for model-specific blobs. |
| **index** | Read **user_metadata + analysis_metadata + tags** → build OpenSearch document; no new canonical writes. |
| **finalize** | Mark completion; optional **seal** ingest metadata. |

**Reprocessing:** new **`pipeline_run`** row; stages overwrite their **namespace** in **`analysis_metadata`**; tags from **`pipeline`** may be **replaced** by “delete all `source='pipeline'` for document + re-insert” or **versioned** in phase 2.

---

## 7. API design (sketch)

| Operation | Sketch |
|-----------|--------|
| **Multipart intake** | Optional **`metadata`** form field: JSON string → parsed into **`user_metadata`** (validate size, e.g. ≤ 32 KiB). |
| **URL intake** | Optional **`metadata`** in JSON body alongside `url`, `title`, `collection_id`. |
| **GET document** | Include **`user_metadata`**, **`analysis_metadata`** (or split: `GET .../metadata` for large payloads), and **`tags`** array (from `document_tags`). |
| **PATCH document metadata** | `PATCH /api/v1/documents/{id}/metadata` — merge or replace **`user_metadata`** keys; **tags** with `source=user` (validate tag length/count). |
| **Internal worker** | Repository helpers: `merge_analysis_metadata(session, document_id, section, dict)`, `replace_pipeline_tags(session, document_id, tags, run_id)`. |

**Authorization:** same as document read/write today; **analysis_metadata** is **read-only** for normal users, **writable** only by worker (DB role or app service path).

---

## 8. OpenSearch / search index

- Denormalize for the index document, e.g.:

  - `tags: ["legal", "nda"]` (union or filter by min confidence)  
  - `metadata_flat` keyword fields for known keys you want to facet  
  - optional **nested** objects for entities

- **Rebuild:** reindex from Postgres (`documents` + `document_tags` + JSONB); **no** need to store full analysis in OpenSearch if Postgres remains source of truth—index **projections** only.

---

## 9. Security and abuse

- **Size caps** on **`user_metadata`** and per-stage **`analysis_metadata`** (configurable bytes).
- **Sanitize** strings used as tags (length, charset; reject control characters).
- **SSRF / URL** metadata already constrained elsewhere; do not **execute** metadata as code.
- **PII:** classify keys in policy (e.g. `user_metadata` may hold reference ids only); log access for sensitive deployments.

---

## 10. Versioning and merge semantics

- **`schema_version`** inside each **`analysis_metadata`** subtree (integer) lets workers migrate shapes.
- **Phase 1:** **replace** entire `extract` / `enrich` / `tagging` objects on successful stage completion.
- **Phase 2:** **field-level** merge with **tombstones** or **per-key `updated_at` + writer** for conflict resolution; optional **metadata history** table (append-only snapshots on each run completion).

---

## 11. Rollout phases

| Phase | Deliverable |
|-------|-------------|
| **P0 — DDL** | Migration adds **`user_metadata`**, **`analysis_metadata`** on **`documents`**, **`document_tags`** table + indexes; comments and constraints. |
| **P1 — Intake** | Accept optional metadata on **multipart** and **`from-url`**; persist to **`user_metadata`**; copy safe **source** hints into **`document_sources.raw_metadata`**. |
| **P2 — Read API** | Expose metadata + tags on **GET document** (and list **summary** optional: e.g. tag list only). |
| **P3 — Pipeline** | In **extract** / **enrich**, write **`analysis_metadata`** and **`document_tags`**; wire **`pipeline_run_id`**. |
| **P4 — PATCH** | User tag and **`user_metadata`** updates. |
| **P5 — Search** | OpenSearch mapping + indexer reading new fields. |

---

## 12. Appendix A — Example DDL (migration `003` sketch)

*Not applied in the repository until an implementation PR wires ORM, APIs, and tests. Adjust names/types to match review.*

```sql
-- documents: client-visible and worker-written JSON blobs
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS user_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS analysis_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN documents.user_metadata IS
  'Client/integration-supplied JSON; intake and PATCH; ACL follows document.';
COMMENT ON COLUMN documents.analysis_metadata IS
  'Pipeline-written sections (extract, enrich, tagging, etc.); not end-user editable.';

CREATE INDEX IF NOT EXISTS ix_documents_user_metadata_gin
  ON documents USING gin (user_metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS ix_documents_analysis_metadata_gin
  ON documents USING gin (analysis_metadata jsonb_path_ops);

CREATE TABLE document_tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
  tag text NOT NULL,
  tag_normalized text NOT NULL,
  source text NOT NULL,
  pipeline_run_id uuid REFERENCES pipeline_runs (id) ON DELETE SET NULL,
  confidence numeric(6, 5),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT document_tags_tag_nonempty_chk CHECK (length(trim(tag)) > 0),
  CONSTRAINT document_tags_tag_normalized_nonempty_chk CHECK (length(trim(tag_normalized)) > 0),
  CONSTRAINT document_tags_source_chk CHECK (
    source IN ('user', 'pipeline', 'rule', 'import')
  ),
  CONSTRAINT document_tags_confidence_chk CHECK (
    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
  )
);

CREATE UNIQUE INDEX uq_document_tags_doc_norm_source
  ON document_tags (document_id, tag_normalized, source);

CREATE INDEX ix_document_tags_document_id ON document_tags (document_id);
CREATE INDEX ix_document_tags_tag_normalized ON document_tags (tag_normalized);

CREATE TRIGGER trg_document_tags_updated_at
  BEFORE UPDATE ON document_tags
  FOR EACH ROW EXECUTE PROCEDURE verifiedsignal_set_updated_at();
```

**Rollback sketch:** drop trigger/table/indexes/columns in reverse order (see paired `003_document_metadata.down.sql` when implemented).

---

## 13. Appendix B — Example `user_metadata` payload (intake)

```json
{
  "integration": {
    "crm_id": "opp-88421",
    "uploaded_by": "alice@example.com"
  },
  "custom": {
    "matter_code": "M-1024",
    "jurisdiction": "US-CA"
  }
}
```

---

## 14. Related documents

- **[`db/README.md`](../db/README.md)** — migrations and schema philosophy  
- **[`docs/url-ingest.md`](url-ingest.md)** — URL intake and source metadata  
- **[`docs/end-user/documents.md`](end-user/documents.md)** — current user-facing document flows (extend when P1–P2 ship)  
- **`app/pipeline/constants.py`** — stage names to align writers  

---

## 15. Summary

Use **`document_sources.raw_metadata`** for **raw provenance**, **`documents.user_metadata`** for **client/integration** fields, **`documents.analysis_metadata`** as **namespaced JSON** for **extract/enrich/tagging** outputs, and **`document_tags`** for **filterable labels** with **source** and **confidence**. Wire pipeline stages to **replace** their namespace on success, record **`pipeline_run_id`** on tags, and **project** a flattened shape into **OpenSearch** when you enable real search.
