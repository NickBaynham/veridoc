"""Derive unique per-organization collection slugs from display names."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Collection

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def collection_slug_base(name: str) -> str:
    """Lowercase slug segment from a human-readable name (matches DB slug check)."""
    raw = name.strip().lower()
    s = _SLUG_RE.sub("-", raw).strip("-")
    return s or "collection"


def next_unique_collection_slug(
    session: Session,
    organization_id: uuid.UUID,
    base: str,
    *,
    ignore_collection_id: uuid.UUID | None = None,
) -> str:
    """Return a slug unique for (organization_id, slug) within ``collections``."""
    base = (base or "collection")[:200].strip("-") or "collection"
    candidate = base
    suffix = 2
    while True:
        stmt = select(Collection.id).where(
            Collection.organization_id == organization_id,
            Collection.slug == candidate,
        )
        if ignore_collection_id is not None:
            stmt = stmt.where(Collection.id != ignore_collection_id)
        stmt = stmt.limit(1)
        if session.scalar(stmt) is None:
            return candidate
        candidate = f"{base}-{suffix}"[:200]
        suffix += 1
