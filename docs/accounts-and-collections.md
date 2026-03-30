# Your account and collections (end users)

The complete **end-user documentation** is in **[`end-user/README.md`](end-user/README.md)** (start there).

**Workspace and collections** in detail: **[`end-user/workspace-and-collections.md`](end-user/workspace-and-collections.md)**.

## Quick summary

- After you obtain an **access token** ([`end-user/signing-in.md`](end-user/signing-in.md)), the first **Bearer** request to a protected route—or an explicit **`POST /auth/sync-identity`**—can create your Postgres **user**, **personal organization**, and **Inbox** when auto-provision is enabled.
- Use **`GET /api/v1/collections`** to list collections and their **ids**; supply **`collection_id`** on uploads when your environment requires it (typical in production).

Operator and JWT details: [`auth-supabase.md`](auth-supabase.md), [`tenancy-postgres.md`](tenancy-postgres.md).
