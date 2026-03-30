# Status and troubleshooting

## Is the service up?

### Overall health

**`GET /api/v1/health`**

**No authentication required.**

**Response (JSON)** includes a top-level **`status`** (for example **`ok`** or **`degraded`**) and component fields:

- **`database`** — **`up`** / **`down`**
- **`redis`** — **`up`** / **`down`**
- **`object_storage`** — **`up`** / **`down`**
- **`opensearch`** — **`up`** / **`down`**

In **non-production** environments, error responses may include **redacted connection hints** (for example a database DSN preview without the password) to help developers. Production responses are usually less detailed.

Use this endpoint for **load balancers** and **uptime checks**.

### Service information

**`GET /api/v1/info`**

**No authentication required.**

Returns **`service` name**, **`environment`**, **`api_prefix`**, and short **notes** about architecture (e.g. OpenSearch as a derived index).

## Common HTTP status codes

| Code | Typical meaning | What to do |
|------|-----------------|------------|
| **200** | Success | — |
| **202** | Accepted (URL ingest) | Poll document detail |
| **204** | Success, no body (delete) | — |
| **400** | Bad input (validation, URL policy) | Read **`detail`** message |
| **401** | Missing/invalid auth | Log in or refresh token |
| **403** | Forbidden (e.g. sync-identity without provision path) | Contact admin or enable provisioning |
| **404** | Not found or no access | Check id and permissions |
| **502** | Upstream storage failure on upload | Retry or contact support with **`document_id`** if returned |
| **503** | Auth not configured or dependency unavailable | Contact operator |

## Document-specific issues

| Problem | Checks |
|---------|--------|
| Upload rejected for size | Reduce file size or ask for a higher limit |
| URL ingest **400** | URL may be blocked for security; try a public HTTPS URL |
| Stuck in **`created`** (URL) | Worker or queue may be down—check **`GET /api/v1/health`** |
| **`enqueue_error` set** | Job queue problem; document may still exist in storage |
| **404** on a document you expect | Wrong id, or your account cannot see that collection |

## Where to get help

1. **Your administrator** — deployment-specific URLs, auth mode, and quotas.
2. **Interactive docs** — `BASE/` (Swagger) on a running server.
3. **Technical docs** in this repo — [`../auth-supabase.md`](../auth-supabase.md), [`../url-ingest.md`](../url-ingest.md), [`../tenancy-postgres.md`](../tenancy-postgres.md).

## Back to the guide

- [End-user guide index](README.md)
- [Getting started](getting-started.md)
