"""
Execute a single model version build: load context, run type-specific builder, persist summary.

Called from ARQ worker (asyncio.to_thread) or synchronously when USE_FAKE_QUEUE=true in tests.
Idempotent: if version is already terminal (completed/failed), no-op.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.repositories import knowledge_model_repository as km_repo
from app.services.models.builders.base import ModelBuildContext
from app.services.models.builders.dispatch import get_builder

log = logging.getLogger("verifiedsignal.knowledge_model.build")


def run_build_knowledge_model_version_sync(model_version_id: str) -> None:
    vid = uuid.UUID(model_version_id)
    SessionLocal = get_session_factory()
    session: Session = SessionLocal()
    try:
        _run_build(session, vid)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run_build(session: Session, version_id: uuid.UUID) -> None:
    version = km_repo.get_version(session, version_id)
    if version is None:
        log.warning("model_build_missing_version version_id=%s", version_id)
        return
    if version.build_status in ("completed", "failed"):
        log.info(
            "model_build_skip_terminal version_id=%s status=%s",
            version_id,
            version.build_status,
        )
        return

    model = km_repo.get_model(session, version.knowledge_model_id)
    if model is None:
        km_repo.update_version_build_state(
            session,
            version_id,
            build_status="failed",
            error_message="knowledge_model missing",
            completed=True,
        )
        return

    # Latest build run for this version (created at enqueue time)
    from sqlalchemy import select

    from app.db.models import ModelBuildRun

    run_row = session.scalars(
        select(ModelBuildRun)
        .where(ModelBuildRun.model_version_id == version_id)
        .order_by(ModelBuildRun.created_at.desc())
        .limit(1)
    ).first()

    try:
        km_repo.update_version_build_state(session, version_id, build_status="building")
        if run_row:
            km_repo.update_build_run(session, run_row.id, status="running")

        doc_ids = km_repo.list_asset_document_ids(session, version_id)
        ctx = ModelBuildContext(
            session=session,
            knowledge_model_id=model.id,
            model_version_id=version_id,
            model_type=model.model_type,
            collection_id=model.collection_id,
            document_ids=doc_ids,
            build_profile=dict(version.build_profile_json or {}),
            version_number=version.version_number,
        )
        builder = get_builder(model.model_type)
        result = builder(ctx)

        km_repo.update_version_build_state(
            session,
            version_id,
            build_status="completed",
            summary_json=result.summary,
            completed=True,
        )
        if run_row:
            km_repo.update_build_run(
                session,
                run_row.id,
                status="completed",
                metrics_json=result.metrics,
            )
        log.info("model_build_ok version_id=%s model_id=%s", version_id, model.id)
    except Exception as e:
        log.exception("model_build_failed version_id=%s", version_id)
        msg = str(e)[:4000]
        km_repo.update_version_build_state(
            session,
            version_id,
            build_status="failed",
            error_message=msg,
            completed=True,
        )
        if run_row:
            km_repo.update_build_run(session, run_row.id, status="failed", error_message=msg)
