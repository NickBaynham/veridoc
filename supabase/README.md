# Local Supabase (optional)

VerifiedSignal session auth (`/auth/*`) targets **Supabase GoTrue**. For local development:

1. Install the [Supabase CLI](https://supabase.com/docs/guides/cli). From the repo root, **`make install-supabase`** uses Homebrew when `brew` is on your `PATH` (requires Docker for the next step).
2. From the repository root run:

   ```bash
   supabase init
   supabase start
   ```

3. Run **`supabase status --output json`** and copy into the repo root **`.env`**:
   - **`API_URL`** → **`SUPABASE_URL`**
   - **`ANON_KEY`** → **`SUPABASE_ANON_KEY`**
   - **`SERVICE_ROLE_KEY`** → **`SUPABASE_SERVICE_ROLE_KEY`**
   - **`JWT_SECRET`** → **`SUPABASE_JWT_SECRET`**

4. Set **`SUPABASE_URL`** to the **`API_URL`** value from step 3 (typically **`http://127.0.0.1:54321`**). The VerifiedSignal API **rewrites loopback hosts to `host.docker.internal` when the process runs inside Docker** (see `effective_supabase_url_for_server` in `app/core/config.py`), so the same **`.env`** works for **`pdm run api`** on the host and for **`docker compose`** **`app`**. **`docker-compose.yml`** adds **`host.docker.internal`** via `extra_hosts` on Linux too. Restart **`app`** after changing **`.env`**.

5. You can still set **`SUPABASE_URL=http://host.docker.internal:54321`** explicitly for Compose-only setups; it is unchanged by the rewrite when already using that hostname.

The FastAPI app validates access tokens with **JWKS** (hosted) or **HS256 + `SUPABASE_JWT_SECRET`** (CLI local); it does **not** call Supabase on every protected request.

For Docker-wide orchestration, prefer `supabase start` (official stack). The root `docker-compose.yml` remains focused on app Postgres/Redis/MinIO/OpenSearch.
