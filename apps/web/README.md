# VerifiedSignal Web (React + Vite)

## UI demo (mock data)

This app ships a **clickable product demo** aligned with the [VerifiedSignal use case spec](https://docs.google.com/document/d/1VpqZqnLtpwi7g64vcXpUSYbyYX8bn84clidrQ-NjtLc/edit) (login, dashboard, upload + pipeline, document reader, collection analytics, search, reports, billing, security). **All domain data is mocked** under `src/demo/` so you can show stakeholders the intended UX before FastAPI endpoints are complete.

- Run locally: `npm install` then `npm run dev` (default [http://127.0.0.1:5173](http://127.0.0.1:5173)).
- Sign in with **any password ≥ 3 characters** (demo only; no network call).
- Replace mock modules with `fetch`/`EventSource` calls to `import.meta.env.VITE_API_URL` when wiring the backend.

## Production auth (later)

The SPA should use **Supabase JS** only where the auth spec requires it (e.g. password reset from emailed link); **login, signup, logout, and refresh** should call the FastAPI API (`VITE_API_URL`) so the refresh token stays **httpOnly** on the API origin. See [`docs/auth-supabase.md`](../../docs/auth-supabase.md) at the repo root.

After you receive an access token, either call **`POST /auth/sync-identity`** with `Authorization: Bearer …` or hit any protected API route: the backend can **create your Postgres user, personal org, and Inbox** automatically (see **[`docs/accounts-and-collections.md`](../../docs/accounts-and-collections.md)**).

## Setup

```bash
cd apps/web
npm install
cp .env.example .env.local   # optional; VITE_* for future API wiring
npm run dev
```

## Build

```bash
npm run build
npm run preview   # serve dist
```
