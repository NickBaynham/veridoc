"""Persistence helpers for document intake (Postgres canonical)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentScore, DocumentSource

if TYPE_CHECKING:
    pass


def create_intake_row_created(
    session: Session,
    *,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    original_filename: str,
    content_type: str | None,
    file_size: int,
    title: str | None,
    user_metadata: dict | None = None,
) -> Document:
    """
    Insert canonical row in `created` before object storage upload completes.

    Tradeoff: a brief window exists where Postgres references bytes not yet in MinIO;
    `ingest_error` + `failed` status recover if upload fails.
    """
    doc = Document(
        id=document_id,
        collection_id=collection_id,
        title=title or original_filename,
        status="created",
        original_filename=original_filename,
        content_type=content_type,
        file_size=file_size,
        row_schema_version=2,
        user_metadata=user_metadata or {},
    )
    session.add(doc)
    session.flush()
    return doc


def create_url_intake_row(
    session: Session,
    *,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    original_filename: str,
    title: str | None,
    canonical_url: str,
    user_metadata: dict | None = None,
) -> Document:
    """
    Insert `documents` (`created`, no storage yet) plus a `document_sources` row (`url`).

    The worker uploads bytes; `finalize_intake_after_upload` adds the `upload` source.
    """
    doc = Document(
        id=document_id,
        collection_id=collection_id,
        title=title or original_filename,
        status="created",
        original_filename=original_filename,
        content_type=None,
        file_size=None,
        row_schema_version=2,
        user_metadata=user_metadata or {},
    )
    session.add(doc)
    session.flush()
    session.add(
        DocumentSource(
            document_id=document_id,
            source_kind="url",
            locator=canonical_url,
            mime_type=None,
            byte_length=None,
            raw_metadata={"phase": "intake_url_submitted"},
        ),
    )
    session.flush()
    return doc


def mark_intake_failed(session: Session, document_id: uuid.UUID, message: str) -> None:
    doc = session.get(Document, document_id)
    if doc is None:
        return
    doc.status = "failed"
    doc.ingest_error = message[:8192]


def finalize_intake_after_upload(
    session: Session,
    *,
    document_id: uuid.UUID,
    storage_key: str,
    bucket: str,
    content_type: str | None,
    file_size: int,
) -> None:
    doc = session.get(Document, document_id)
    if doc is None:
        raise ValueError(f"document not found: {document_id}")
    doc.storage_key = storage_key
    doc.status = "queued"
    doc.file_size = file_size
    doc.content_type = content_type
    src = DocumentSource(
        document_id=document_id,
        source_kind="upload",
        locator=f"s3://{bucket}/{storage_key}",
        mime_type=content_type,
        byte_length=file_size,
        raw_metadata={"bucket": bucket, "storage_key": storage_key, "phase": "intake_raw"},
    )
    session.add(src)


def mark_enqueue_failed(session: Session, document_id: uuid.UUID, message: str) -> None:
    doc = session.get(Document, document_id)
    if doc is None:
        return
    doc.enqueue_error = message[:8192]


def get_document(session: Session, document_id: uuid.UUID) -> Document | None:
    return session.get(Document, document_id)


def get_document_by_storage_key(session: Session, storage_key: str) -> Document | None:
    stmt = select(Document).where(Document.storage_key == storage_key).limit(1)
    return session.scalars(stmt).first()


def list_documents_in_collections(
    session: Session,
    collection_ids: list[uuid.UUID],
    *,
    limit: int,
    offset: int,
) -> list[Document]:
    if not collection_ids:
        return []
    stmt = (
        select(Document)
        .where(Document.collection_id.in_(collection_ids))
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt).all())


def count_documents_in_collections(session: Session, collection_ids: list[uuid.UUID]) -> int:
    if not collection_ids:
        return 0
    stmt = (
        select(func.count()).select_from(Document).where(Document.collection_id.in_(collection_ids))
    )
    return int(session.scalar(stmt) or 0)


def list_sources_for_document(session: Session, document_id: uuid.UUID) -> list[DocumentSource]:
    stmt = (
        select(DocumentSource)
        .where(DocumentSource.document_id == document_id)
        .order_by(DocumentSource.created_at)
    )
    return list(session.scalars(stmt).all())


def delete_document_row(session: Session, document_id: uuid.UUID) -> bool:
    """Hard delete; `document_sources` rows cascade. Returns False if missing."""
    doc = session.get(Document, document_id)
    if doc is None:
        return False
    session.delete(doc)
    return True


def count_documents_with_storage_key(session: Session, storage_key: str) -> int:
    stmt = select(func.count()).select_from(Document).where(Document.storage_key == storage_key)
    return int(session.scalar(stmt) or 0)


def count_documents_with_extract_artifact_key(session: Session, extract_artifact_key: str) -> int:
    stmt = (
        select(func.count())
        .select_from(Document)
        .where(Document.extract_artifact_key == extract_artifact_key)
    )
    return int(session.scalar(stmt) or 0)


def avg_canonical_factuality_for_collection(
    session: Session, collection_id: uuid.UUID
) -> float | None:
    """Mean canonical factuality_score for documents in the collection (None if no scores)."""
    stmt = (
        select(func.avg(DocumentScore.factuality_score))
        .select_from(DocumentScore)
        .join(Document, Document.id == DocumentScore.document_id)
        .where(
            Document.collection_id == collection_id,
            DocumentScore.is_canonical.is_(True),
            DocumentScore.factuality_score.isnot(None),
        )
    )
    v = session.scalar(stmt)
    return float(v) if v is not None else None


def max_document_updated_at_for_collection(session: Session, collection_id: uuid.UUID):
    """Latest `documents.updated_at` in the collection, or None if empty."""
    stmt = select(func.max(Document.updated_at)).where(Document.collection_id == collection_id)
    return session.scalar(stmt)


def count_documents_by_status_for_collection(
    session: Session, collection_id: uuid.UUID
) -> dict[str, int]:
    stmt = (
        select(Document.status, func.count())
        .where(Document.collection_id == collection_id)
        .group_by(Document.status)
    )
    return {row[0]: int(row[1]) for row in session.execute(stmt)}


def primary_source_kind_for_documents(
    session: Session, document_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """
    Earliest `document_sources` row per document (by created_at) → source_kind.
    """
    if not document_ids:
        return {}
    rn = (
        func.row_number()
        .over(
            partition_by=DocumentSource.document_id,
            order_by=DocumentSource.created_at.asc(),
        )
        .label("rn")
    )
    subq = (
        select(DocumentSource.document_id, DocumentSource.source_kind, rn)
        .where(DocumentSource.document_id.in_(document_ids))
        .subquery()
    )
    stmt = select(subq.c.document_id, subq.c.source_kind).where(subq.c.rn == 1)
    return {row[0]: row[1] for row in session.execute(stmt)}


def list_collection_documents_page(
    session: Session,
    collection_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    status: str | None = None,
    q: str | None = None,
    source_kind: str | None = None,
    sort: str = "created_at_desc",
) -> tuple[list[tuple[Document, DocumentScore | None]], int]:
    """
    Paginated documents in one collection with optional filters and canonical score (outer join).

    sort: created_at_desc | created_at_asc | name_asc | name_desc | factuality_desc | factuality_asc
    """
    filters = [Document.collection_id == collection_id]
    if status:
        filters.append(Document.status == status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Document.title.ilike(term),
                Document.original_filename.ilike(term),
            ),
        )
    if source_kind and source_kind.strip():
        sk = source_kind.strip()
        filters.append(
            exists(
                select(1)
                .select_from(DocumentSource)
                .where(
                    DocumentSource.document_id == Document.id,
                    DocumentSource.source_kind == sk,
                ),
            ),
        )

    count_stmt = select(func.count()).select_from(Document).where(*filters)
    total = int(session.scalar(count_stmt) or 0)

    stmt = (
        select(Document, DocumentScore)
        .outerjoin(
            DocumentScore,
            (DocumentScore.document_id == Document.id) & (DocumentScore.is_canonical.is_(True)),
        )
        .where(*filters)
    )
    name_expr = func.coalesce(Document.title, Document.original_filename, "")

    if sort == "created_at_asc":
        stmt = stmt.order_by(Document.created_at.asc(), Document.id.asc())
    elif sort == "name_asc":
        stmt = stmt.order_by(name_expr.asc(), Document.id.asc())
    elif sort == "name_desc":
        stmt = stmt.order_by(name_expr.desc(), Document.id.asc())
    elif sort == "factuality_asc":
        stmt = stmt.order_by(
            DocumentScore.factuality_score.asc().nullslast(),
            Document.created_at.desc(),
        )
    elif sort == "factuality_desc":
        stmt = stmt.order_by(
            DocumentScore.factuality_score.desc().nullslast(),
            Document.created_at.desc(),
        )
    else:
        # created_at_desc (default)
        stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())

    stmt = stmt.limit(limit).offset(offset)
    rows = list(session.execute(stmt).all())
    return [(d, s) for d, s in rows], total
