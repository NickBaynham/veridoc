# Getting started

## What VerifiedSignal is (today)

VerifiedSignal is a **document intelligence platform** under active development. In the current phase it focuses on:

- **Secure sign-in** (optional Supabase-backed email/password through this API).
- **Storing documents** you upload or point to by URL, in **collections** tied to your workspace.
- **Background processing** (a worker queue runs a pipeline scaffold on each document).
- **APIs** to list and inspect documents, check service health, and (later) search an index derived from your data.

The canonical copy of document metadata lives in **PostgreSQL**; **OpenSearch** is intended for search and is not fully connected yet.

## How you interact with the product

1. **HTTP API** — The primary interface. All versioned resources live under a prefix, usually **`/api/v1`**. Session-style auth routes are under **`/auth`** (no `/api/v1` prefix).
2. **Browser UI demo** — The React app in `apps/web` is a **clickable mock** for demos; it does not yet drive all real APIs. See the [web README](../../apps/web/README.md).

Your organization’s deployment will give you a **base URL** (for example `https://api.example.com`). Every example below uses a placeholder:

```text
BASE = https://your-api-host.example
```

## Interactive API documentation

When the API server is running, open the root URL in a browser (for example `https://your-api-host.example/`). You get **Swagger UI** (interactive OpenAPI) where you can try requests if the server allows it.

- **ReDoc:** `BASE/redoc`
- **OpenAPI JSON:** `BASE/openapi.json`

Protected routes need an **`Authorization: Bearer <access_token>`** header. Obtain a token via **`POST /auth/login`** (see [Signing in and tokens](signing-in.md)).

## Typical first-time flow

1. Sign up or receive an account (see [Signing in](signing-in.md)).
2. Log in and store the **access token** (and use the **refresh** flow before it expires).
3. Optionally call **`POST /auth/sync-identity`** or simply call any protected route so your **personal workspace and Inbox** are created (see [Workspace and collections](workspace-and-collections.md)).
4. **`GET /api/v1/collections`** — pick a **collection id** for uploads.
5. **`POST /api/v1/documents`** (file) or **`POST /api/v1/documents/from-url`** (JSON) — add a document.
6. **`GET /api/v1/documents/{id}`** — poll until status shows processing has advanced or failed.

## Limits you should know about

Exact numbers depend on server configuration (your admin can change them):

- **Uploaded file size:** capped by a server setting (often on the order of tens of megabytes). If you exceed it, the API returns an error describing the limit.
- **URL ingest:** the fetched body size is capped similarly; timeouts and redirect limits apply. See [Documents — URL](documents.md#submitting-a-document-by-url) and [`../url-ingest.md`](../url-ingest.md).
- **List pagination:** document list supports `limit` (up to 200) and `offset` query parameters.

## Privacy and data location

Where files and database rows live depends on **your deployment** (cloud region, your company’s servers, etc.). This guide does not assume a specific host—ask your administrator for data residency and retention policies.

## Next steps

- [Signing in and tokens](signing-in.md)
- [Workspace and collections](workspace-and-collections.md)
