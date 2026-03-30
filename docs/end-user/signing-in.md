# Signing in and tokens

VerifiedSignal can use **Supabase Auth** behind the scenes. Your client talks to **this API’s `/auth` routes** so that **refresh tokens** can stay in an **httpOnly cookie** (more secure than storing long-lived secrets in browser JavaScript).

> **Note:** If the server is not configured with Supabase (`SUPABASE_URL` and keys), auth routes may return **503**. Your administrator must enable auth for your environment.

## Sign up

**`POST /auth/signup`**  
JSON body: `email`, `password`

- You may need to **confirm your email** before you can sign in (depends on Supabase project settings).
- Response is a short confirmation message, not an access token.

## Log in

**`POST /auth/login`**  
JSON body: `email`, `password`

**Response (JSON)** includes:

- **`access_token`** — JWT. Send this as **`Authorization: Bearer <access_token>`** on **`/api/v1/...`** routes.
- **`expires_in`** — lifetime of the access token in seconds (typical values come from your Supabase project).

**Cookie:** The API also sets an httpOnly cookie **`vs_refresh_token`** on path **`/auth`**. Browsers send it automatically to **`/auth/refresh`** and **`/auth/logout`** when your frontend calls those URLs on the **same API origin** and **CORS** is configured for credentials.

### Single-page apps (SPAs)

- Keep **`access_token` in memory** (not `localStorage` if you can avoid it).
- Call **`POST /auth/refresh`** (with credentials/cookies enabled) before the access token expires to obtain a new one.
- Ensure your dev server origin is listed in the API’s **CORS** allowed origins so cookies and `Authorization` headers work.

Details for developers: [`../auth-supabase.md`](../auth-supabase.md).

## Refresh the session

**`POST /auth/refresh`**  
Uses the **`vs_refresh_token`** cookie (no JSON body required for cookie-based refresh).

**Response:** new **`access_token`** and **`expires_in`**. The cookie may be rotated.

If refresh fails, you need to **log in again**.

## Log out

**`POST /auth/logout`**  
Attempts to invalidate the session server-side and clears the refresh cookie. You should **discard the access token** in the client.

## Password reset email

**`POST /auth/reset-password`**  
JSON body: `email`

The API returns a generic success message. If the email exists, Supabase sends reset instructions. (Exact wording depends on provider configuration.)

## After you have an access token

1. Send **`Authorization: Bearer <access_token>`** on every protected **`/api/v1/...`** request.
2. **First use:** the API can **create your Postgres user, personal organization, and Inbox** automatically (default). See [Workspace and collections](workspace-and-collections.md).
3. Optional explicit step: **`POST /auth/sync-identity`** with the same Bearer header returns your database user id and collection ids—useful if the UI wants a clear “workspace ready” moment.

## Common problems

| Symptom | What to check |
|--------|----------------|
| **401 Not authenticated** | Missing or wrong `Authorization` header; token expired—refresh or log in again. |
| **401 Invalid or expired token** | Clock skew is rare; usually the token really expired or the wrong secret/JWKS is in use between environments. |
| **503 Supabase auth is not configured** | Server missing Supabase env vars—contact the operator. |
| **Cookie not sent on refresh** | Wrong API origin, path, or CORS; cookie is scoped to **`/auth`**. |

## Next steps

- [Workspace and collections](workspace-and-collections.md)
- [Documents](documents.md)
