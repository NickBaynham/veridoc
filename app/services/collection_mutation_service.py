"""Create, update, and delete collections for authenticated users."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Collection
from app.repositories import collection_repository as coll_repo
from app.services.collection_slug import collection_slug_base, next_unique_collection_slug
from app.services.document_access import resolve_accessible_collection_ids
from app.services.exceptions import CollectionAccessError, CollectionOrgAccessError
from app.services.identity_service import find_user_id_by_auth_sub

log = logging.getLogger("verifiedsignal.collections")


def _user_can_access_org(
    session: Session,
    auth_sub: str,
    organization_id: uuid.UUID,
    settings: Settings,
) -> bool:
    """True if the caller is a member of ``organization_id`` or dev fallback matches that org."""
    user_id = find_user_id_by_auth_sub(session, auth_sub)
    if user_id is not None:
        row = session.execute(
            text(
                """
                SELECT 1 FROM organization_members
                WHERE user_id = :uid AND organization_id = :org
                LIMIT 1
                """
            ),
            {"uid": user_id, "org": organization_id},
        ).fetchone()
        if row is not None:
            return True
    if (
        settings.allow_default_collection_fallback
        and settings.default_collection_id is not None
    ):
        col = coll_repo.get_collection_by_id(session, settings.default_collection_id)
        if col is not None and col.organization_id == organization_id:
            return True
    return False


def resolve_organization_id_for_create(
    session: Session,
    auth_sub: str,
    organization_id: uuid.UUID | None,
    settings: Settings,
) -> uuid.UUID:
    """
    Pick target org for a new collection.

    If ``organization_id`` is set, it must be one the caller may use (membership or dev fallback).
    If omitted, use the caller's first membership org, else the org of the default collection when
    fallback is enabled.
    """
    if organization_id is not None:
        if not _user_can_access_org(session, auth_sub, organization_id, settings):
            raise CollectionOrgAccessError()
        return organization_id

    user_id = find_user_id_by_auth_sub(session, auth_sub)
    if user_id is not None:
        row = session.execute(
            text(
                """
                SELECT organization_id FROM organization_members
                WHERE user_id = :uid
                ORDER BY organization_id
                LIMIT 1
                """
            ),
            {"uid": user_id},
        ).fetchone()
        if row is not None:
            return row[0]

    if (
        settings.allow_default_collection_fallback
        and settings.default_collection_id is not None
    ):
        col = coll_repo.get_collection_by_id(session, settings.default_collection_id)
        if col is not None:
            return col.organization_id

    raise CollectionOrgAccessError(
        "No workspace organization available; specify organization_id or complete account setup"
    )


def _assert_collection_mutable(
    session: Session, auth_sub: str, collection_id: uuid.UUID
) -> Collection:
    settings = get_settings()
    allowed = set(resolve_accessible_collection_ids(session, auth_sub, settings))
    if collection_id not in allowed:
        raise CollectionAccessError()
    col = coll_repo.get_collection_by_id(session, collection_id)
    if col is None:
        raise CollectionAccessError()
    return col


def create_collection_for_user(
    session: Session,
    auth_sub: str,
    *,
    name: str,
    organization_id: uuid.UUID | None,
) -> Collection:
    settings = get_settings()
    trimmed = name.strip()
    if not trimmed:
        raise ValueError("Collection name is required")

    org_id = resolve_organization_id_for_create(session, auth_sub, organization_id, settings)
    base = collection_slug_base(trimmed)
    slug = next_unique_collection_slug(session, org_id, base)
    col = Collection(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=trimmed,
        slug=slug,
    )
    session.add(col)
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        log.warning("collection_create_integrity err=%s", type(e).__name__)
        raise ValueError("Could not create collection (slug conflict)") from e
    session.refresh(col)
    return col


def update_collection_for_user(
    session: Session,
    auth_sub: str,
    *,
    collection_id: uuid.UUID,
    name: str,
) -> Collection:
    trimmed = name.strip()
    if not trimmed:
        raise ValueError("Collection name is required")

    col = _assert_collection_mutable(session, auth_sub, collection_id)
    base = collection_slug_base(trimmed)
    slug = next_unique_collection_slug(
        session, col.organization_id, base, ignore_collection_id=col.id
    )
    col.name = trimmed
    col.slug = slug
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        log.warning("collection_update_integrity err=%s", type(e).__name__)
        raise ValueError("Could not rename collection (slug conflict)") from e
    session.refresh(col)
    return col


def delete_collection_for_user(
    session: Session, auth_sub: str, *, collection_id: uuid.UUID
) -> None:
    _assert_collection_mutable(session, auth_sub, collection_id)
    col = coll_repo.get_collection_by_id(session, collection_id)
    if col is None:
        raise CollectionAccessError()
    session.delete(col)
    session.commit()
