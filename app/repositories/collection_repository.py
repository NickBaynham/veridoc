"""Collections visible within tenant boundaries."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Collection, Document


def get_collection_by_id(session: Session, collection_id: uuid.UUID) -> Collection | None:
    return session.get(Collection, collection_id)


def list_collections_by_ids(session: Session, collection_ids: list[uuid.UUID]) -> list[Collection]:
    if not collection_ids:
        return []
    stmt = select(Collection).where(Collection.id.in_(collection_ids)).order_by(Collection.name)
    return list(session.scalars(stmt).all())


def count_documents_per_collection(
    session: Session,
    collection_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not collection_ids:
        return {}
    stmt = (
        select(Document.collection_id, func.count())
        .where(Document.collection_id.in_(collection_ids))
        .group_by(Document.collection_id)
    )
    return {row[0]: int(row[1]) for row in session.execute(stmt)}
