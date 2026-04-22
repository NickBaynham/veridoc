# Security and dependency audits

## Hardening (high level)

- **`ENVIRONMENT=staging`** — Treated like production for client-visible surfaces: `/health` omits dependency error/DSN detail; Swagger/OpenAPI stay off unless `EXPOSE_OPENAPI_DOCS=true`.
- **`ENVIRONMENT=production|prod`** — Additionally logs startup warnings for `USE_FAKE_*` and for `VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK=true` (risky multi-tenant default).
- **`VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK`** — Defaults `false`; set `true` in local dev when using the seeded default inbox (see `.env.example`).
- **Rate limits** — `slowapi` on `/auth/*` and document intake (`RATE_LIMIT_*`, `RATE_LIMIT_ENABLED` in `.env.example`). In-memory per API process (not shared across replicas).

## Auditing dependencies

CI runs **pip-audit** on exported Python requirements and **npm audit** in `apps/web` (see [.github/workflows/ci.yml](../.github/workflows/ci.yml)). Refresh locks occasionally (`pdm lock` / `pdm update`, Dependabot PRs for npm).

**Python (mirror CI):**

```bash
pdm export -f requirements --without-hashes -o /tmp/requirements-audit.txt
pdm run pip-audit -r /tmp/requirements-audit.txt
```

**Web:**

```bash
cd apps/web && npm audit
```

If you use **uv** with `uv.lock`, keep it aligned with `pyproject.toml`; CI uses PDM and does not validate `uv.lock`.
