"""
Map Supabase JWT `sub` to Postgres `users` and personal org/collection (tenancy bootstrap).

Idempotent: safe on every authenticated request when auto-provision is enabled.
"""

from __future__ import annotations

import logging
import re
import uuid

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.claims import AccessTokenClaims
from app.core.config import Settings

log = logging.getLogger("verifiedsignal.identity")


def slug_fragment_from_sub(sub: str, *, max_len: int = 48) -> str:
    """Lowercase slug segment derived from `sub` (for internal placeholder emails / org slugs)."""
    raw = sub.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    if not s:
        s = "user"
    return s[:max_len].rstrip("-") or "user"


def placeholder_email_for_sub(sub: str) -> str:
    """Deterministic synthetic email when the JWT has no usable `email` claim."""
    frag = slug_fragment_from_sub(sub, max_len=64)
    return f"{frag}@users.verifiedsignal.internal"


def normalized_email_for_claims(claims: AccessTokenClaims) -> str:
    """Return a unique, lowercased email for the users row."""
    sub = claims.sub.strip()
    if claims.email and str(claims.email).strip():
        try:
            return validate_email(
                str(claims.email).strip(),
                check_deliverability=False,
            ).normalized.lower()
        except EmailNotValidError:
            pass
    return placeholder_email_for_sub(sub)


def find_user_id_by_auth_sub(session: Session, auth_sub: str) -> uuid.UUID | None:
    """
    Match JWT subject to `users.id` (UUID) and/or `users.external_sub` (string).
    """
    sub = auth_sub.strip()
    uid: uuid.UUID | None = None
    try:
        uid = uuid.UUID(sub)
    except ValueError:
        uid = None

    if uid is not None:
        row = session.execute(
            text("SELECT id FROM users WHERE id = :uid OR external_sub = :sub"),
            {"uid": uid, "sub": sub},
        ).fetchone()
    else:
        row = session.execute(
            text("SELECT id FROM users WHERE external_sub = :sub"),
            {"sub": sub},
        ).fetchone()
    if row is None:
        return None
    return row[0]


def _pick_user_id(sub: str, session: Session) -> uuid.UUID:
    """Prefer Supabase UUID `sub` when valid; avoid PK collisions with unrelated rows."""
    sub_stripped = sub.strip()
    try:
        candidate = uuid.UUID(sub_stripped)
    except ValueError:
        return uuid.uuid4()
    row = session.execute(
        text("SELECT id, external_sub FROM users WHERE id = :id"),
        {"id": candidate},
    ).fetchone()
    if row is None:
        return candidate
    existing_sub = row[1]
    if existing_sub is None or existing_sub == sub_stripped:
        return candidate
    return uuid.uuid4()


def ensure_personal_tenant_for_claims(
    session: Session,
    claims: AccessTokenClaims,
    settings: Settings,
) -> tuple[uuid.UUID | None, bool]:
    """
    Ensure users, organizations, organization_members, and a default collections row exist.

    Returns (database user id, whether to commit). If auto-provision is off and there is no
    user row yet, returns (None, False).
    """
    existing = find_user_id_by_auth_sub(session, claims.sub)
    if existing is not None:
        return existing, False

    if not settings.auto_provision_identity:
        return None, False

    sub = claims.sub.strip()
    email = normalized_email_for_claims(claims)
    display_name = (claims.display_name or "").strip() or None
    user_id = _pick_user_id(sub, session)
    org_id = uuid.uuid4()
    collection_id = uuid.uuid4()
    org_slug = f"personal-{user_id.hex[:26]}"

    try:
        session.execute(
            text(
                """
                INSERT INTO users (id, email, display_name, external_sub)
                VALUES (:id, :email, :display_name, :external_sub)
                """
            ),
            {
                "id": user_id,
                "email": email,
                "display_name": display_name,
                "external_sub": sub,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO organizations (id, name, slug)
                VALUES (:id, :name, :slug)
                """
            ),
            {"id": org_id, "name": "Personal workspace", "slug": org_slug},
        )
        session.execute(
            text(
                """
                INSERT INTO organization_members (organization_id, user_id, role)
                VALUES (:organization_id, :user_id, 'owner')
                """
            ),
            {"organization_id": org_id, "user_id": user_id},
        )
        session.execute(
            text(
                """
                INSERT INTO collections (id, organization_id, name, slug)
                VALUES (:id, :organization_id, :name, :slug)
                """
            ),
            {
                "id": collection_id,
                "organization_id": org_id,
                "name": "Inbox",
                "slug": "inbox",
            },
        )
    except IntegrityError as e:
        session.rollback()
        log.info("identity_provision_race sub=%s err=%s", sub, type(e).__name__)
        again = find_user_id_by_auth_sub(session, claims.sub)
        if again is not None:
            return again, False
        raise

    log.info(
        "identity_provisioned user_id=%s org_id=%s collection_id=%s",
        user_id,
        org_id,
        collection_id,
    )
    return user_id, True


def list_tenant_ids_for_user(
    session: Session,
    user_id: uuid.UUID,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Organization and collection UUIDs visible via `organization_members` for this user."""
    org_rows = session.execute(
        text(
            """
            SELECT organization_id FROM organization_members
            WHERE user_id = :uid
            ORDER BY organization_id
            """
        ),
        {"uid": user_id},
    ).fetchall()
    org_ids = [r[0] for r in org_rows]
    col_rows = session.execute(
        text(
            """
            SELECT c.id FROM collections c
            INNER JOIN organization_members om ON c.organization_id = om.organization_id
            WHERE om.user_id = :user_id
            ORDER BY c.created_at
            """
        ),
        {"user_id": user_id},
    ).fetchall()
    col_ids = [r[0] for r in col_rows]
    return org_ids, col_ids
