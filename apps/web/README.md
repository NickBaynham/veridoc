# VerifiedSignal Web (React + Vite)

## Modes

### Demo mode (default)

If **`VITE_API_URL`** is unset or empty, the app uses **mock data** under `src/demo/` and **client-only login** (password ≥ 3 characters, no network). Demo **delete** removes a document from the in-session list (stored in `sessionStorage` under `verifiedsignal_demo_deleted_docs`). Use this for stakeholder UX reviews without running the API.

### API mode

Set **`VITE_API_URL`** to your FastAPI origin (no trailing slash), e.g. `http://127.0.0.1:8000` in `.env.local`.

- **Auth:** `POST /auth/login` with JSON `{ "email", "password" }`, `credentials: 'include'` so the API can set the httpOnly refresh cookie on `/auth`. The access token is kept in memory and also stored in **`sessionStorage`** under `verifiedsignal_api_access_token` so full page reloads and deep links keep working when the refresh cookie is absent (common in local dev). It is removed on **Sign out**. Prefer relying on the refresh cookie in production and treat sessionStorage as a dev convenience; it is XSS-sensitive if third-party scripts run on the same origin.
- **CORS:** the API must list this SPA’s origin in **`CORS_ORIGINS`** (see root `docs/auth-supabase.md`).
- **Supabase:** `/auth/login` returns **503** if Supabase env vars are missing on the API — configure the backend per `docs/auth-supabase.md`.

**Wired endpoints (UI):**

| Area | Endpoints |
|------|-----------|
| Session | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` |
| Profile | `GET /api/v1/users/me` |
| Dashboard | `GET /api/v1/documents`, `GET /api/v1/collections`, `GET /api/v1/events/stream` (SSE with `?access_token=`; see `docs/end-user/search-and-events.md`) |
| Document reader | `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/file?redirect=false` (download original), `DELETE /api/v1/documents/{id}` (`canonical_score` when present — heuristic and/or HTTP scorer; see `docs/scoring-http.md`) |
| Upload | `POST /api/v1/documents` (multipart), `POST /api/v1/documents/from-url`, poll `GET /api/v1/documents/{id}/pipeline` — see **Local folder (below)** |
| Search | `GET /api/v1/search` with optional `collection_id`, `content_type`, `status`, `ingest_source`, repeated `tags`, `include_facets` (Bearer required by default on the API). Demo mode mirrors these filters on mock hits and shows a static facet table when enabled. |
| Collections | `GET /api/v1/collections`, `POST /api/v1/collections`, `PATCH /api/v1/collections/{id}`, `DELETE /api/v1/collections/{id}`, `GET /api/v1/collections/{id}/analytics` — **Collections** page wires list + create + rename + delete (demo: `sessionStorage` key `verifiedsignal_demo_collections_v1`) |

**Still mock / placeholder:** Reports, Billing, Security pages; demo-style histogram/trend **charts** on the analytics page (API mode adds real facet tables + Postgres KPIs). Search “mode” toggles (keyword / semantic / hybrid) are UI-only until the API supports them.

### Local folder (`/library/upload` → **Local folder** tab)

The SPA can ingest an entire **directory tree** from the user’s machine and optionally **keep documents aligned** with that folder using only browser APIs plus the same HTTP routes as single-file upload.

- **Choose folder…** — uses `<input webkitdirectory>` so every supported browser can select a tree; each file is uploaded with **`POST /api/v1/documents`** (title defaults to the **relative path** inside the pick).
- **Grant folder access** (Chromium / Edge) — uses the **File System Access API** (`showDirectoryPicker`) so the app can re-read the folder without a new picker dialog.
- **Sync** (API mode): compares the current tree to a **path → `{ document_id, lastModified, size }`** map stored in **`localStorage`** (`verifiedsignal:localDirSync:v1`). New paths are uploaded; changed files (mtime/size) trigger **delete + re-upload**; paths gone from disk call **`DELETE /api/v1/documents/{id}`**. **Auto-sync every 60s** runs only when a live directory handle exists (Chromium).
- **Limits:** sync state is **per browser profile**, not a server-side watched directory. Safari/Firefox users typically re-pick the folder for each sync unless the browser adds `showDirectoryPicker`. Details for operators and API fields: **[`docs/end-user/documents.md`](../../docs/end-user/documents.md)** (*Local folder ingestion*).

## Setup

```bash
cd apps/web
npm install
cp .env.example .env.local   # API mode: ensures VITE_API_URL (or: `make web-config` from repo root)
npm run dev
```

From the repository root you can run **`make web-config`** (creates **`.env.local`** if missing) and **`make web-dev`** (runs Vite). Configure **`CORS_ORIGINS`** and **Supabase** in the root **`.env`** when using the Docker API — see the root **README** section *Web UI against the Docker API*.

## Tests

```bash
npm run test:unit              # Vitest (API URL helpers, etc.)
npm run test:e2e               # Playwright — demo mode (no VITE_API_URL)
npm run test:e2e:api-mock      # Playwright — API mode with in-browser HTTP mocks
npm run test:e2e:ui            # Playwright UI mode
```

API-mode E2E starts Vite with `VITE_API_URL=http://127.0.0.1:17654` (nothing listens there); `e2e/helpers/apiMockRoutes.ts` fulfills requests so CI does not need Postgres or Supabase.

## Build

```bash
npm run build
npm run preview   # serve dist
```

## Production auth notes

Use **Supabase** only where the auth spec requires it (e.g. password reset from an emailed link). **Login, signup, logout, refresh** should go through FastAPI so the refresh token stays **httpOnly** on the API origin. See [`docs/auth-supabase.md`](../../docs/auth-supabase.md) and [`docs/end-user/README.md`](../../docs/end-user/README.md).
