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

4. **If FastAPI runs inside Docker** (`docker compose` **`app`** service), **`127.0.0.1:54321` is wrong** from inside the container (it is not your Mac). Set **`SUPABASE_URL=http://host.docker.internal:54321`** instead (same keys as above). **`docker-compose.yml`** adds **`host.docker.internal`** for Linux as well. Restart **`app`** after changing **`.env`**.

5. **If FastAPI runs on the host** (`pdm run api` / **`make api-local`**), **`SUPABASE_URL=http://127.0.0.1:54321`** is correct.

The FastAPI app validates access tokens with **JWKS** (hosted) or **HS256 + `SUPABASE_JWT_SECRET`** (CLI local); it does **not** call Supabase on every protected request.

For Docker-wide orchestration, prefer `supabase start` (official stack). The root `docker-compose.yml` remains focused on app Postgres/Redis/MinIO/OpenSearch.
