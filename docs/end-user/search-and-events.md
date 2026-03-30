# Search and live updates

## Search

**`GET /api/v1/search?q=...&limit=...`**

- **`q`** — search text (can be empty; max length enforced by the server)
- **`limit`** — 1–100, default 10

**Auth today:** the route accepts requests **with or without** a Bearer token. The principal is not yet used to filter results in the stub implementation.

### Current behavior (preview)

The implementation is a **placeholder** until OpenSearch is fully wired:

- **`hits`** is usually an empty list
- **`index_status`** is **`stub`**
- **`message`** explains that the index is disposable and rebuildable from Postgres

You can still call the endpoint to **verify connectivity** and to keep client code ready for real results later.

## Live updates (Server-Sent Events)

**`GET /api/v1/events/stream`**

Returns a **text/event-stream** (SSE) connection. Your client should use **`EventSource`** (browser) or an SSE-capable HTTP client.

**Auth today:** like search, this route uses a **placeholder** optional principal—connections are not yet restricted per user in code you ship today. **Do not rely on this for confidential data** until your deployment adds real auth on the stream.

### What you will see

1. First, a **`connected`** event (JSON with `type` and empty `payload`).
2. Later, JSON lines with:
   - **`type`** — event name (for example **`document_queued`** after a successful file upload enqueue)
   - **`payload`** — structured details (e.g. `document_id`, `job_id`, `storage_key`)
   - **`ts`** — UTC timestamp
   - **`environment`** — server environment label

Events are broadcast **in memory** on a single API instance. Multi-server deployments will need a shared bus (for example Redis) for all users to see the same events—your operator’s roadmap.

### Using SSE in the browser

```javascript
const es = new EventSource(`${API_BASE}/api/v1/events/stream`);
es.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  console.log(msg.type, msg.payload);
};
```

Handle **`onerror`** to reconnect with backoff if the network drops.

## Next steps

- [Status and troubleshooting](status-and-troubleshooting.md)
- [Documents](documents.md) — what happens before `document_queued` fires
