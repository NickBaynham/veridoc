"""Move or copy documents between collections (same access rules as list/get)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Document, DocumentScore, DocumentSource, DocumentTag
from app.repositories import document_repository as doc_repo
from app.services.document_access import resolve_accessible_collection_ids
from app.services.document_metadata_service import (
    flatten_analysis_for_search_text,
    tags_union_for_index,
)
from app.services.exceptions import IntakeValidationError, TargetCollectionAccessError
from app.services.opensearch_document_index import index_document_sync
from app.services.text_embedding_stub import deterministic_text_embedding
from app.services.user_metadata import (
    extract_metadata_label,
    flatten_metadata_for_search_text,
)

log = logging.getLogger(__name__)


def reindex_document_search(
    session: Session,
    document_id: uuid.UUID,
    settings: Settings | None = None,
) -> None:
    """Push current Postgres fields for one document into OpenSearch (best-effort)."""
    settings = settings or get_settings()
    doc = session.get(Document, document_id)
    if doc is None:
        return
    sources = doc_repo.list_sources_for_document(session, document_id)
    ingest_source = "url" if any(s.source_kind == "url" for s in sources) else "upload"
    meta = doc.user_metadata or {}
    tags = tags_union_for_index(session, document_id, meta)
    metadata_label = extract_metadata_label(meta)
    umeta_text = flatten_metadata_for_search_text(meta)
    ameta_text = flatten_analysis_for_search_text(doc.analysis_metadata or {})
    metadata_text = f"{umeta_text}\n{ameta_text}".strip()[:8000]
    embed_text = " ".join(
        x for x in (doc.title or "", (doc.body_text or "")[:12000]) if x
    )
    embedding = deterministic_text_embedding(embed_text, dim=64)
    try:
        index_document_sync(
            document_id=doc.id,
            collection_id=doc.collection_id,
            title=doc.title,
            body_text=doc.body_text,
            status=doc.status,
            settings=settings,
            content_type=doc.content_type,
            original_filename=doc.original_filename,
            ingest_source=ingest_source,
            tags=tags,
            metadata_label=metadata_label,
            metadata_text=metadata_text,
            embedding=embedding,
        )
    except Exception as e:
        log.warning("reindex_after_transfer_failed document_id=%s err=%s", document_id, e)


def move_document_for_user(
    session: Session,
    auth_sub: str,
    *,
    document_id: uuid.UUID,
    target_collection_id: uuid.UUID,
    settings: Settings | None = None,
) -> Document | None:
    """
    Change `documents.collection_id` when source and target are both visible to the caller.

    Returns None if the document is missing or not visible (same as GET semantics).
    """
    settings = settings or get_settings()
    allowed = set(resolve_accessible_collection_ids(session, auth_sub, settings))
    doc = doc_repo.get_document(session, document_id)
    if doc is None or doc.collection_id not in allowed:
        return None
    if target_collection_id not in allowed:
        raise TargetCollectionAccessError()
    if doc.collection_id == target_collection_id:
        raise IntakeValidationError("Document is already in that collection.")
    doc.collection_id = target_collection_id
    session.commit()
    session.refresh(doc)
    reindex_document_search(session, document_id, settings)
    return doc


def copy_document_for_user(
    session: Session,
    auth_sub: str,
    *,
    document_id: uuid.UUID,
    target_collection_id: uuid.UUID,
    settings: Settings | None = None,
) -> Document | None:
    """
    Insert a new document row (+ sources + score rows) reusing storage keys when present.

    Object bytes are shared until every referencing row is deleted (reference counting in delete).
    """
    settings = settings or get_settings()
    allowed = set(resolve_accessible_collection_ids(session, auth_sub, settings))
    src = doc_repo.get_document(session, document_id)
    if src is None or src.collection_id not in allowed:
        return None
    if target_collection_id not in allowed:
        raise TargetCollectionAccessError()

    new_id = uuid.uuid4()
    umeta = dict(src.user_metadata or {})
    new_doc = Document(
        id=new_id,
        collection_id=target_collection_id,
        title=src.title,
        external_key=src.external_key,
        content_sha256=src.content_sha256,
        status=src.status,
        row_schema_version=src.row_schema_version,
        original_filename=src.original_filename,
        content_type=src.content_type,
        file_size=src.file_size,
        storage_key=src.storage_key,
        ingest_error=src.ingest_error,
        enqueue_error=src.enqueue_error,
        body_text=src.body_text,
        extract_artifact_key=src.extract_artifact_key,
        user_metadata=umeta,
        analysis_metadata=dict(src.analysis_metadata or {}),
    )
    session.add(new_doc)
    session.flush()

    for s in doc_repo.list_sources_for_document(session, document_id):
        session.add(
            DocumentSource(
                id=uuid.uuid4(),
                document_id=new_id,
                source_kind=s.source_kind,
                locator=s.locator,
                mime_type=s.mime_type,
                byte_length=s.byte_length,
                raw_metadata=dict(s.raw_metadata or {}),
            ),
        )

    for tg in session.scalars(select(DocumentTag).where(DocumentTag.document_id == document_id)):
        session.add(
            DocumentTag(
                id=uuid.uuid4(),
                document_id=new_id,
                tag=tg.tag,
                tag_normalized=tg.tag_normalized,
                source=tg.source,
                pipeline_run_id=None,
                confidence=tg.confidence,
            ),
        )

    score_rows = list(
        session.scalars(select(DocumentScore).where(DocumentScore.document_id == document_id)),
    )
    for sc in score_rows:
        session.add(
            DocumentScore(
                id=uuid.uuid4(),
                document_id=new_id,
                pipeline_run_id=None,
                scorer_name=sc.scorer_name,
                scorer_version=sc.scorer_version,
                score_schema_version=sc.score_schema_version,
                scored_at=sc.scored_at or datetime.now(UTC),
                is_canonical=sc.is_canonical,
                factuality_score=sc.factuality_score,
                ai_generation_probability=sc.ai_generation_probability,
                fallacy_score=sc.fallacy_score,
                confidence_score=sc.confidence_score,
                score_payload=dict(sc.score_payload or {}),
            ),
        )

    session.commit()
    session.refresh(new_doc)
    reindex_document_search(session, new_id, settings)
    return new_doc
