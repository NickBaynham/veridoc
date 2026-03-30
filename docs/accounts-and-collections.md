# Your account and collections (end users)

VerifiedSignal ties **Supabase login** to **Postgres**: your documents live in **collections**, and each collection belongs to an **organization** you are a member of.

## What happens when you sign in

1. You get a **JWT access token** from the API (for example after `POST /auth/login`).
2. The first time you call a protected API route with `Authorization: Bearer <token>`, the backend can **create your tenant data automatically** (when `VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY` is enabled, which is the default):
   - a row in **`users`** linked to your Supabase id (`sub`);
   - a **personal organization** (“Personal workspace”);
   - **membership** as **owner**;
   - a default **Inbox** collection.

This is **idempotent**: later requests reuse the same rows.

## Optional explicit step

If you prefer to provision before other calls (for example to show “workspace ready” in the UI), call:

```http
POST /auth/sync-identity
Authorization: Bearer <access_token>
```

The response includes your Postgres `database_user_id`, `organization_ids`, and `collection_ids`.

## Checking your profile

```http
GET /api/v1/users/me
Authorization: Bearer <access_token>
```

Returns the JWT `user_id` (`sub`) and, when linked, `database_user_id`, plus `email` / `display_name` from the token when present.

## Uploads and collection choice

- If the API accepts an optional **`collection_id`**, send your **Inbox** (or another) collection UUID from `GET /api/v1/collections` or from the sync response.
- In **production**, operators often disable the **default shared inbox** fallback so uploads must target a real collection. See [`docs/auth-supabase.md`](auth-supabase.md).
