# Workspace and collections

## Concepts

- **Organization** — A tenant boundary (your team or personal workspace). You belong to one or more via **membership**.
- **Collection** — A folder-like group of **documents** inside an organization. Permissions today follow **“can access collection if you are a member of its organization.”**
- **Inbox** — When your account is first provisioned, you typically receive a default collection named **Inbox** in your **personal workspace** (unless your deployment uses a different onboarding flow).

## Automatic setup from your login

When **`VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY`** is enabled (default in many deployments):

1. You complete [sign-in](signing-in.md) and obtain an **access token**.
2. The **first protected API call** with `Authorization: Bearer …` can create, if missing:
   - your **user** record (linked to your Supabase id),
   - a **personal organization**,
   - **owner** membership,
   - an **Inbox** collection.

This is safe to repeat; it does not duplicate your workspace.

## Optional: sync identity explicitly

**`POST /auth/sync-identity`**  
**Headers:** `Authorization: Bearer <access_token>`

**Response (JSON)** includes:

- **`database_user_id`** — internal user id in Postgres
- **`organization_ids`** — orgs you belong to
- **`collection_ids`** — collections visible through those orgs

Use this if your app wants a dedicated “prepare workspace” step right after login.

## List your collections

**`GET /api/v1/collections`**  
**Headers:** `Authorization: Bearer <access_token>`

**Response:** `collections` array. Each item includes **`id`**, **`name`**, **`slug`**, **`organization_id`**, **`document_count`**, and timestamps.

Use a collection’s **`id`** as **`collection_id`** when uploading files or submitting URLs (see [Documents](documents.md)).

## Manage collections (create, rename, delete)

You can add collections, change their display **name**, and remove collections you are allowed to manage. The server stores a URL-style **`slug`** per organization (derived from the name, unique within that org). Renaming updates **`name`** and recomputes **`slug`**.

### Web app

On the **Collections** page (`/collections` in **`apps/web`**):

- **New collection** — enter a name and choose **Create** (API mode calls the backend; demo mode keeps rows in **`sessionStorage`** under **`verifiedsignal_demo_collections_v1`**).
- **Rename** — opens an inline editor; **Save** commits the new name (demo: updates slug locally).
- **Delete** — asks for confirmation, then removes the collection. **In API mode, documents in that collection are removed** (database cascade); treat this as irreversible.

### HTTP API (Bearer required)

| Method | Path | Body (JSON) | Success |
|--------|------|-------------|---------|
| **POST** | `/api/v1/collections` | **`name`** (string, required). Optional **`organization_id`** (UUID) — must be an organization you belong to; if omitted, the API picks a permitted workspace org (same rules as other collection APIs). | **201** — created collection (includes **`id`**, **`slug`**, **`document_count`** starting at **0**). |
| **PATCH** | `/api/v1/collections/{collection_id}` | **`name`** (string, required, non-blank). | **200** — updated collection ( **`document_count`** reflects current rows). |
| **DELETE** | `/api/v1/collections/{collection_id}` | — | **204** — empty body. |

Typical errors:

- **400** — invalid or empty name, or other validation failures.
- **403** — you cannot create a collection in the given **`organization_id`** (not a member).
- **404** — collection missing or not accessible to your account (same shape as other protected routes).
- **409** — rare **`slug`** collision after rename/create (retry with a slightly different name).

## Collection analytics

**`GET /api/v1/collections/{collection_id}/analytics`** (Bearer required, same access rules as the collection) returns **index facets** (ingest source, status, content type, tags) and **Postgres rollups** over canonical document scores. See [Search and live updates — Collection analytics](search-and-events.md#collection-analytics).

## Your profile

**`GET /api/v1/users/me`**  
**Headers:** `Authorization: Bearer <access_token>`

**Response (JSON)** includes:

- **`user_id`** — the JWT subject (Supabase user id)
- **`database_user_id`** — linked Postgres user when provisioned
- **`email`**, **`display_name`** — when present in the token claims

## Choosing a collection for new documents

- Prefer the **Inbox** (or another collection) from **`GET /api/v1/collections`**.
- Some deployments allow **omitting** `collection_id` on upload; the server then uses a configured default (often a shared dev inbox). **Production** setups may require an explicit **`collection_id`** so content never lands in the wrong place—ask your administrator.

Operator-focused detail: [`../tenancy-postgres.md`](../tenancy-postgres.md), [`../auth-supabase.md`](../auth-supabase.md).

## Next steps

- [Documents](documents.md)
- [Search and live updates](search-and-events.md)
