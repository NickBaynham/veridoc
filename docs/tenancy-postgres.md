# Tenancy in Postgres (operators)

## Model

- **`users`** — human actors; `external_sub` stores the Supabase JWT `sub` (string or UUID string).
- **`organization_members`** — many-to-many with roles (`owner`, `admin`, `member`, `viewer`).
- **`collections`** — scoped to an organization; document ACLs use collection membership via org membership.

## Auto-provision from JWT

When **`VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY=true`** (default), every successful Bearer validation runs an idempotent check:

1. Find `users` by `id = UUID(sub)` or `external_sub = sub`.
2. If missing, insert **user** (email from JWT or synthetic `…@users.verifiedsignal.internal`), **organization** (`personal-<hex>` slug), **owner membership**, and **Inbox** collection.

The auth dependency **commits** when inserts occur so the same request’s downstream handlers see the new rows (separate DB sessions still read committed data).

Implementation: `app/services/identity_service.py`, wired from `app/auth/dependencies.py` (`get_current_user`).

## Default inbox fallback (legacy dev)

If **no** `users` row matches the JWT:

- With **`VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK=true`** (default) and **`VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID`** set, ACL resolution returns only that seeded collection (migration **002**).
- With fallback **disabled**, ACL returns **no** collections until a user row exists — intended for **production / multi-tenant** deployments.

Intake without `collection_id` also requires fallback (or an explicit default collection id); when fallback is **false**, clients must send **`collection_id`**.

## Dedicated hook

**`POST /auth/sync-identity`** performs the same provisioning as the auth dependency and returns org/collection ids. Useful for SPAs that want an explicit post-login step.

## Related docs

- [`auth-supabase.md`](auth-supabase.md) — JWT, session routes, env vars.
- [`end-user/README.md`](end-user/README.md) — full end-user guide.
- [`accounts-and-collections.md`](accounts-and-collections.md) — short pointer + quick summary.
