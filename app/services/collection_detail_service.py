"""Collection workspace detail and document directory (Postgres-backed)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.repositories import collection_repository as coll_repo
from app.repositories import document_repository as doc_repo
from app.repositories import pipeline_repository as pipe_repo
from app.schemas.collection import (
    CollectionActivityItemOut,
    CollectionActivityResponse,
    CollectionDetailOut,
    CollectionDocumentItemOut,
    CollectionDocumentsListResponse,
)
from app.schemas.document import CanonicalScoreOut
from app.services.document_access import resolve_accessible_collection_ids

_IN_PROGRESS_STATUSES = frozenset({"created", "queued"})


def get_collection_detail_for_user(
    session: Session,
    *,
    auth_sub: str,
    collection_id: uuid.UUID,
    settings: Settings | None = None,
) -> CollectionDetailOut | None:
    """
    Return collection summary for workspace header if the caller can access it.

    `description` is reserved for a future DB column; always None today.
    """
    settings = settings or get_settings()
    accessible = resolve_accessible_collection_ids(session, auth_sub, settings)
    if collection_id not in accessible:
        return None
    coll = coll_repo.get_collection_by_id(session, collection_id)
    if coll is None:
        return None
    counts = coll_repo.count_documents_per_collection(session, [collection_id])
    document_count = counts.get(collection_id, 0)
    last_updated = doc_repo.max_document_updated_at_for_collection(session, collection_id)
    status_breakdown = doc_repo.count_documents_by_status_for_collection(session, collection_id)
    failed_document_count = int(status_breakdown.get("failed", 0))
    in_progress_document_count = sum(int(status_breakdown.get(s, 0)) for s in _IN_PROGRESS_STATUSES)
    avg_factuality = doc_repo.avg_canonical_factuality_for_collection(session, collection_id)
    return CollectionDetailOut(
        id=coll.id,
        organization_id=coll.organization_id,
        name=coll.name,
        slug=coll.slug,
        description=None,
        document_count=document_count,
        last_updated=last_updated,
        status_breakdown=status_breakdown,
        failed_document_count=failed_document_count,
        in_progress_document_count=in_progress_document_count,
        avg_canonical_factuality=avg_factuality,
        created_at=coll.created_at,
    )


def _score_to_out(row) -> CanonicalScoreOut | None:
    if row is None:
        return None
    return CanonicalScoreOut(
        factuality_score=float(row.factuality_score) if row.factuality_score is not None else None,
        ai_generation_probability=float(row.ai_generation_probability)
        if row.ai_generation_probability is not None
        else None,
        fallacy_score=float(row.fallacy_score) if row.fallacy_score is not None else None,
        confidence_score=float(row.confidence_score) if row.confidence_score is not None else None,
        scorer_name=row.scorer_name,
        scorer_version=row.scorer_version,
    )


def list_collection_documents_for_user(
    session: Session,
    *,
    auth_sub: str,
    collection_id: uuid.UUID,
    limit: int,
    offset: int,
    status: str | None = None,
    q: str | None = None,
    source_kind: str | None = None,
    sort: str = "created_at_desc",
    settings: Settings | None = None,
) -> CollectionDocumentsListResponse | None:
    """Paginated directory of documents in a collection, or None if collection inaccessible."""
    settings = settings or get_settings()
    accessible = resolve_accessible_collection_ids(session, auth_sub, settings)
    if collection_id not in accessible:
        return None
    if coll_repo.get_collection_by_id(session, collection_id) is None:
        return None

    rows, total = doc_repo.list_collection_documents_page(
        session,
        collection_id,
        limit=limit,
        offset=offset,
        status=status,
        q=q,
        source_kind=source_kind,
        sort=sort,
    )
    doc_ids = [d.id for d, _ in rows]
    kinds = doc_repo.primary_source_kind_for_documents(session, doc_ids)
    items: list[CollectionDocumentItemOut] = []
    for doc, score_row in rows:
        base = CollectionDocumentItemOut.model_validate(doc)
        items.append(
            base.model_copy(
                update={
                    "canonical_score": _score_to_out(score_row),
                    "primary_source_kind": kinds.get(doc.id),
                },
            ),
        )
    return CollectionDocumentsListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        collection_id=collection_id,
    )


def get_collection_activity_for_user(
    session: Session,
    *,
    auth_sub: str,
    collection_id: uuid.UUID,
    limit: int = 100,
    settings: Settings | None = None,
) -> CollectionActivityResponse | None:
    """Recent pipeline events for documents in this collection."""
    settings = settings or get_settings()
    accessible = resolve_accessible_collection_ids(session, auth_sub, settings)
    if collection_id not in accessible:
        return None
    if coll_repo.get_collection_by_id(session, collection_id) is None:
        return None
    cap = max(1, min(limit, 200))
    rows = pipe_repo.list_recent_events_for_collection(session, collection_id, limit=cap)
    items = [
        CollectionActivityItemOut(
            id=ev.id,
            document_id=doc.id,
            document_title=doc.title,
            pipeline_run_id=run.id,
            event_type=ev.event_type,
            stage=ev.stage,
            step_index=ev.step_index,
            payload=ev.payload or {},
            created_at=ev.created_at,
        )
        for ev, run, doc in rows
    ]
    return CollectionActivityResponse(items=items, collection_id=collection_id)


