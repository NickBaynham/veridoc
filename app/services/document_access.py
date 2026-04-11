"""Resolve which collections a caller may read (documents in those collections are visible)."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.identity_service import find_user_id_by_auth_sub


def resolve_accessible_collection_ids(
    session: Session,
    auth_sub: str,
    settings: Settings,
) -> list[uuid.UUID]:
    """
    JWT `sub` is matched to `users.id` (UUID) or `users.external_sub` (string).

    If a row exists, return collection ids for orgs that user belongs to.

    If no user row exists: when `VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK` is true and
    `VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID` is set, return that single id (legacy local dev).
    Otherwise return no collections (use with auto-provision or explicit provisioning).

    When a user row exists and fallback is enabled, the default collection id is **unioned** with
    org collections so intake that targets `VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID` (multipart
    default) stays visible after auto-provision created a separate personal Inbox UUID.
    """
    user_id = find_user_id_by_auth_sub(session, auth_sub)

    if user_id is None:
        if (
            settings.allow_default_collection_fallback
            and settings.default_collection_id is not None
        ):
            return [settings.default_collection_id]
        return []

    cols = session.execute(
        text(
            """
            SELECT c.id FROM collections c
            INNER JOIN organization_members om ON c.organization_id = om.organization_id
            WHERE om.user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).fetchall()
    out = [r[0] for r in cols]
    if (
        settings.allow_default_collection_fallback
        and settings.default_collection_id is not None
        and settings.default_collection_id not in out
    ):
        out.append(settings.default_collection_id)
    return out
