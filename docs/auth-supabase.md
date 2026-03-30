# Supabase auth integration

## Backend (implemented under `app/`)

- **Settings:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL`, `JWT_ALGORITHM`, `JWT_AUDIENCE`, `CORS_ORIGINS`, `AUTH_COOKIE_SECURE`.
- **JWT validation:** `app/auth/jwt_verify.py` — HS256 with shared secret when `SUPABASE_JWKS_URL` is empty; otherwise RS256 via JWKS. Claims used for provisioning include `sub`, `email`, and optional display hints (`name` / `user_metadata`).
- **Identity + tenancy:** `get_current_user` in `app/auth/dependencies.py` validates the Bearer token (**401** if missing/invalid), then when **`VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY`** is true, ensures `users` + personal org + `organization_members` + default Inbox `collections` exist (idempotent) and **commits** if it inserted rows. See **[`docs/tenancy-postgres.md`](tenancy-postgres.md)**.
- **Session routes:** `app/api/routes/session_auth.py` mounted at `/auth` — signup, login (sets httpOnly refresh cookie on path `/auth`), refresh, logout, reset-password email, and **`POST /auth/sync-identity`** (Bearer only — same provisioning as above, returns org/collection ids).
- **Protected API examples:** `GET/POST /api/v1/documents`, `GET /api/v1/collections`, `GET /api/v1/users/me` (returns `database_user_id` when linked).
- **Multi-tenant / production:** set **`VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK=false`** so JWTs without a `users` row do **not** see the seeded default inbox; keep auto-provision on or manage rows via your own onboarding. **`VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID`** + fallback is mainly for local dev.
- **CORS:** credentials enabled for `CORS_ORIGINS`.

Refresh cookie name: `vs_refresh_token` (path `/auth`).

## Frontend (`apps/web/`)

Scaffold with Vite + React + TypeScript; keep access tokens **in memory only**; call FastAPI for session operations. After login you can call **`POST /auth/sync-identity`** or rely on the first protected API request to provision Postgres. See `apps/web/README.md` and `supabase/README.md`.

**End-user overview:** **[`docs/accounts-and-collections.md`](accounts-and-collections.md)**.

## Tests

`tests/unit/test_session_auth.py` mocks the Supabase client. Integration tests use **`jwt_integration_client`** (real JWT + Postgres, no `get_current_user` override) in `tests/conftest.py` for tenancy flows; other DB-heavy tests may still override `get_current_user`.
