"""Persistence for knowledge_models, versions, assets, and build runs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Document,
    KnowledgeModel,
    KnowledgeModelAsset,
    KnowledgeModelVersion,
    ModelBuildRun,
)


def insert_knowledge_model(
    session: Session,
    *,
    collection_id: uuid.UUID,
    name: str,
    description: str | None,
    model_type: str,
    created_by: uuid.UUID | None,
) -> KnowledgeModel:
    row = KnowledgeModel(
        collection_id=collection_id,
        name=name.strip(),
        description=description.strip() if description else None,
        model_type=model_type,
        status="active",
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row


def insert_model_version(
    session: Session,
    *,
    knowledge_model_id: uuid.UUID,
    version_number: int,
    build_status: str,
    source_selection_snapshot_json: dict,
    build_profile_json: dict,
) -> KnowledgeModelVersion:
    row = KnowledgeModelVersion(
        knowledge_model_id=knowledge_model_id,
        version_number=version_number,
        build_status=build_status,
        source_selection_snapshot_json=source_selection_snapshot_json,
        build_profile_json=build_profile_json,
    )
    session.add(row)
    session.flush()
    return row


def insert_assets(
    session: Session,
    *,
    model_version_id: uuid.UUID,
    document_ids: list[uuid.UUID],
    inclusion_reason: str | None = "user_selected",
) -> None:
    for did in document_ids:
        session.add(
            KnowledgeModelAsset(
                model_version_id=model_version_id,
                document_id=did,
                inclusion_reason=inclusion_reason,
            )
        )


def insert_build_run(
    session: Session,
    *,
    model_version_id: uuid.UUID,
    status: str,
) -> ModelBuildRun:
    now = datetime.now(UTC)
    row = ModelBuildRun(
        model_version_id=model_version_id,
        status=status,
        started_at=now if status == "running" else None,
    )
    session.add(row)
    session.flush()
    return row


def get_model(session: Session, model_id: uuid.UUID) -> KnowledgeModel | None:
    return session.get(KnowledgeModel, model_id)


def get_model_if_in_collection(
    session: Session,
    model_id: uuid.UUID,
    collection_id: uuid.UUID,
) -> KnowledgeModel | None:
    m = session.get(KnowledgeModel, model_id)
    if m is None or m.collection_id != collection_id:
        return None
    return m


def list_models_for_collection(
    session: Session,
    collection_id: uuid.UUID,
) -> list[KnowledgeModel]:
    stmt: Select[tuple[KnowledgeModel]] = (
        select(KnowledgeModel)
        .where(KnowledgeModel.collection_id == collection_id)
        .order_by(KnowledgeModel.updated_at.desc())
    )
    return list(session.scalars(stmt).all())


def get_version(session: Session, version_id: uuid.UUID) -> KnowledgeModelVersion | None:
    return session.get(KnowledgeModelVersion, version_id)


def list_versions_for_model(
    session: Session,
    knowledge_model_id: uuid.UUID,
) -> list[KnowledgeModelVersion]:
    stmt = (
        select(KnowledgeModelVersion)
        .where(KnowledgeModelVersion.knowledge_model_id == knowledge_model_id)
        .order_by(KnowledgeModelVersion.version_number.desc())
    )
    return list(session.scalars(stmt).all())


def get_latest_version(
    session: Session,
    knowledge_model_id: uuid.UUID,
) -> KnowledgeModelVersion | None:
    stmt = (
        select(KnowledgeModelVersion)
        .where(KnowledgeModelVersion.knowledge_model_id == knowledge_model_id)
        .order_by(KnowledgeModelVersion.version_number.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def count_assets_for_version(session: Session, model_version_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(KnowledgeModelAsset).where(
        KnowledgeModelAsset.model_version_id == model_version_id
    )
    return int(session.scalar(stmt) or 0)


def list_asset_document_ids(session: Session, model_version_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(KnowledgeModelAsset.document_id).where(
        KnowledgeModelAsset.model_version_id == model_version_id
    )
    return list(session.scalars(stmt).all())


def list_assets_with_documents(
    session: Session,
    model_version_id: uuid.UUID,
) -> list[tuple[KnowledgeModelAsset, Document]]:
    stmt = (
        select(KnowledgeModelAsset, Document)
        .join(Document, Document.id == KnowledgeModelAsset.document_id)
        .where(KnowledgeModelAsset.model_version_id == model_version_id)
        .order_by(Document.title.asc().nulls_last(), Document.original_filename.asc().nulls_last())
    )
    return list(session.execute(stmt).all())


def update_version_build_state(
    session: Session,
    version_id: uuid.UUID,
    *,
    build_status: str,
    summary_json: dict | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> None:
    v = session.get(KnowledgeModelVersion, version_id)
    if v is None:
        return
    v.build_status = build_status
    if summary_json is not None:
        v.summary_json = summary_json
    if error_message is not None:
        v.error_message = error_message
    if completed and build_status == "completed":
        v.completed_at = datetime.now(UTC)
        v.error_message = None
    elif completed and build_status == "failed":
        v.completed_at = datetime.now(UTC)


def update_build_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    status: str,
    error_message: str | None = None,
    metrics_json: dict | None = None,
) -> None:
    r = session.get(ModelBuildRun, run_id)
    if r is None:
        return
    now = datetime.now(UTC)
    r.status = status
    if status == "running" and r.started_at is None:
        r.started_at = now
    if status in ("completed", "failed"):
        r.completed_at = now
    if error_message is not None:
        r.error_message = error_message
    if metrics_json is not None:
        r.metrics_json = metrics_json


def documents_in_collection(
    session: Session,
    collection_id: uuid.UUID,
    document_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    """Return subset of document_ids that exist and belong to collection."""
    if not document_ids:
        return set()
    stmt = select(Document.id).where(
        Document.collection_id == collection_id,
        Document.id.in_(document_ids),
    )
    return set(session.scalars(stmt).all())
