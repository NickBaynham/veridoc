"""Orchestration: create/list/get knowledge models and trigger builds."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import KnowledgeModel, KnowledgeModelVersion
from app.domain.knowledge_model_constants import MODEL_TYPES
from app.repositories import knowledge_model_repository as km_repo
from app.schemas.knowledge_model import (
    KnowledgeModelAssetListResponse,
    KnowledgeModelAssetOut,
    KnowledgeModelCreateIn,
    KnowledgeModelCreateResponse,
    KnowledgeModelDetailOut,
    KnowledgeModelListItemOut,
    KnowledgeModelListResponse,
    KnowledgeModelVersionDetailOut,
    KnowledgeModelVersionListResponse,
    KnowledgeModelVersionOut,
    KnowledgeModelVersionSummaryOut,
)
from app.services.document_access import resolve_accessible_collection_ids
from app.services.identity_service import find_user_id_by_auth_sub
from app.services.models.model_build_worker import run_build_knowledge_model_version_sync
from app.services.queue_service import enqueue_build_knowledge_model_version_sync


def _ensure_collection_access(
    session: Session,
    auth_sub: str,
    collection_id: uuid.UUID,
    settings: Settings,
) -> None:
    allowed = resolve_accessible_collection_ids(session, auth_sub, settings)
    if collection_id not in allowed:
        raise PermissionError("collection not found or access denied")


def _version_summary(
    session: Session,
    v: KnowledgeModelVersion,
) -> KnowledgeModelVersionSummaryOut:
    n = km_repo.count_assets_for_version(session, v.id)
    return KnowledgeModelVersionSummaryOut(
        id=v.id,
        version_number=v.version_number,
        build_status=v.build_status,
        created_at=v.created_at,
        completed_at=v.completed_at,
        asset_count=n,
        error_message=v.error_message,
    )


def list_models_for_collection(
    session: Session,
    *,
    auth_sub: str,
    collection_id: uuid.UUID,
    settings: Settings | None = None,
) -> KnowledgeModelListResponse:
    settings = settings or get_settings()
    _ensure_collection_access(session, auth_sub, collection_id, settings)
    rows = km_repo.list_models_for_collection(session, collection_id)
    items: list[KnowledgeModelListItemOut] = []
    for m in rows:
        latest = km_repo.get_latest_version(session, m.id)
        items.append(
            KnowledgeModelListItemOut(
                id=m.id,
                collection_id=m.collection_id,
                name=m.name,
                description=m.description,
                model_type=m.model_type,
                status=m.status,
                created_at=m.created_at,
                updated_at=m.updated_at,
                latest_version=_version_summary(session, latest) if latest else None,
            )
        )
    return KnowledgeModelListResponse(items=items, collection_id=collection_id)


def create_model(
    session: Session,
    *,
    auth_sub: str,
    collection_id: uuid.UUID,
    body: KnowledgeModelCreateIn,
    settings: Settings | None = None,
) -> KnowledgeModelCreateResponse:
    settings = settings or get_settings()
    _ensure_collection_access(session, auth_sub, collection_id, settings)

    if body.model_type not in MODEL_TYPES:
        raise ValueError("invalid model_type")

    doc_set = km_repo.documents_in_collection(session, collection_id, body.selected_document_ids)
    if len(doc_set) != len(body.selected_document_ids):
        raise ValueError("one or more documents are missing or not in this collection")

    uid = find_user_id_by_auth_sub(session, auth_sub)
    created_by = uid

    snap: dict[str, Any] = {
        "document_ids": [str(x) for x in body.selected_document_ids],
        "model_type": body.model_type,
    }

    m = km_repo.insert_knowledge_model(
        session,
        collection_id=collection_id,
        name=body.name,
        description=body.description,
        model_type=body.model_type,
        created_by=created_by,
    )
    v = km_repo.insert_model_version(
        session,
        knowledge_model_id=m.id,
        version_number=1,
        build_status="queued",
        source_selection_snapshot_json=snap,
        build_profile_json=body.build_profile or {},
    )
    km_repo.insert_assets(
        session,
        model_version_id=v.id,
        document_ids=body.selected_document_ids,
    )
    br = km_repo.insert_build_run(session, model_version_id=v.id, status="queued")
    session.flush()
    session.commit()

    build_job_id: str | None = None
    if settings.use_fake_queue:
        run_build_knowledge_model_version_sync(str(v.id))
    else:
        build_job_id = enqueue_build_knowledge_model_version_sync(str(v.id))

    session.expire_all()
    m2 = session.get(KnowledgeModel, m.id)
    v2 = session.get(KnowledgeModelVersion, v.id)
    if m2 is None or v2 is None:
        raise RuntimeError("model persist failed")

    km_item = KnowledgeModelListItemOut(
        id=m2.id,
        collection_id=m2.collection_id,
        name=m2.name,
        description=m2.description,
        model_type=m2.model_type,
        status=m2.status,
        created_at=m2.created_at,
        updated_at=m2.updated_at,
        latest_version=_version_summary(session, v2),
    )
    ver_out = KnowledgeModelVersionOut(
        id=v2.id,
        knowledge_model_id=v2.knowledge_model_id,
        version_number=v2.version_number,
        build_status=v2.build_status,
        created_at=v2.created_at,
        completed_at=v2.completed_at,
        error_message=v2.error_message,
        asset_count=km_repo.count_assets_for_version(session, v2.id),
    )
    _ = br.id
    return KnowledgeModelCreateResponse(
        knowledge_model=km_item,
        version=ver_out,
        build_job_id=build_job_id,
    )


def get_model_detail(
    session: Session,
    *,
    auth_sub: str,
    model_id: uuid.UUID,
    settings: Settings | None = None,
) -> KnowledgeModelDetailOut | None:
    settings = settings or get_settings()
    m = km_repo.get_model(session, model_id)
    if m is None:
        return None
    _ensure_collection_access(session, auth_sub, m.collection_id, settings)
    latest = km_repo.get_latest_version(session, m.id)
    summary = latest.summary_json if latest else None
    return KnowledgeModelDetailOut(
        id=m.id,
        collection_id=m.collection_id,
        name=m.name,
        description=m.description,
        model_type=m.model_type,
        status=m.status,
        created_at=m.created_at,
        updated_at=m.updated_at,
        latest_version=_version_summary(session, latest) if latest else None,
        summary_json=summary,
    )


def list_versions(
    session: Session,
    *,
    auth_sub: str,
    model_id: uuid.UUID,
    settings: Settings | None = None,
) -> KnowledgeModelVersionListResponse | None:
    settings = settings or get_settings()
    m = km_repo.get_model(session, model_id)
    if m is None:
        return None
    _ensure_collection_access(session, auth_sub, m.collection_id, settings)
    vers = km_repo.list_versions_for_model(session, model_id)
    items = [
        KnowledgeModelVersionOut(
            id=x.id,
            knowledge_model_id=x.knowledge_model_id,
            version_number=x.version_number,
            build_status=x.build_status,
            created_at=x.created_at,
            completed_at=x.completed_at,
            error_message=x.error_message,
            asset_count=km_repo.count_assets_for_version(session, x.id),
        )
        for x in vers
    ]
    return KnowledgeModelVersionListResponse(items=items, knowledge_model_id=model_id)


def get_version_detail(
    session: Session,
    *,
    auth_sub: str,
    model_id: uuid.UUID,
    version_id: uuid.UUID,
    settings: Settings | None = None,
) -> KnowledgeModelVersionDetailOut | None:
    settings = settings or get_settings()
    m = km_repo.get_model(session, model_id)
    if m is None:
        return None
    _ensure_collection_access(session, auth_sub, m.collection_id, settings)
    v = km_repo.get_version(session, version_id)
    if v is None or v.knowledge_model_id != model_id:
        return None
    return KnowledgeModelVersionDetailOut(
        id=v.id,
        knowledge_model_id=v.knowledge_model_id,
        version_number=v.version_number,
        build_status=v.build_status,
        source_selection_snapshot_json=dict(v.source_selection_snapshot_json or {}),
        build_profile_json=dict(v.build_profile_json or {}),
        summary_json=v.summary_json,
        error_message=v.error_message,
        created_at=v.created_at,
        completed_at=v.completed_at,
        asset_count=km_repo.count_assets_for_version(session, v.id),
    )


def list_version_assets(
    session: Session,
    *,
    auth_sub: str,
    model_id: uuid.UUID,
    version_id: uuid.UUID,
    settings: Settings | None = None,
) -> KnowledgeModelAssetListResponse | None:
    settings = settings or get_settings()
    m = km_repo.get_model(session, model_id)
    if m is None:
        return None
    _ensure_collection_access(session, auth_sub, m.collection_id, settings)
    v = km_repo.get_version(session, version_id)
    if v is None or v.knowledge_model_id != model_id:
        return None
    pairs = km_repo.list_assets_with_documents(session, version_id)
    items = [
        KnowledgeModelAssetOut(
            id=a.id,
            document_id=a.document_id,
            title=d.title,
            original_filename=d.original_filename,
            inclusion_reason=a.inclusion_reason,
            source_weight=float(a.source_weight) if a.source_weight is not None else None,
            created_at=a.created_at,
        )
        for a, d in pairs
    ]
    return KnowledgeModelAssetListResponse(items=items, model_version_id=version_id)
