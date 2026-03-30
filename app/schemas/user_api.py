"""User profile responses (JWT + Postgres identity)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class UserMeOut(BaseModel):
    """Caller identity: Supabase `sub` and optional linked Postgres `users` row."""

    user_id: str = Field(description="JWT subject (Supabase user id)")
    database_user_id: uuid.UUID | None = Field(
        default=None,
        description="Primary key in Postgres `users` when provisioned or pre-seeded",
    )
    email: str | None = Field(default=None, description="Email claim from the access token, if any")
    display_name: str | None = Field(
        default=None,
        description="Display name hint from token claims, if any",
    )


class SyncIdentityOut(BaseModel):
    """Result of `POST /auth/sync-identity` after ensuring Postgres rows exist."""

    database_user_id: uuid.UUID
    organization_ids: list[uuid.UUID]
    collection_ids: list[uuid.UUID]
