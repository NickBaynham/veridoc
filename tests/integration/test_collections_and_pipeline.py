"""Integration: collections API and scaffold pipeline persistence (Postgres)."""

from __future__ import annotations

import uuid

import psycopg
import pytest


@pytest.mark.integration
def test_list_collections_includes_default_inbox(intake_api_client):
    r = intake_api_client.get("/api/v1/collections")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "collections" in data
    assert len(data["collections"]) >= 1
    slugs = {c["slug"] for c in data["collections"]}
    assert "default-inbox" in slugs
    row = next(c for c in data["collections"] if c["slug"] == "default-inbox")
    assert row["name"] == "Default Inbox"
    assert "document_count" in row
    assert row["document_count"] >= 0


@pytest.mark.integration
def test_list_collections_document_count_after_intake(intake_api_client):
    before = intake_api_client.get("/api/v1/collections").json()
    default_before = next(
        c["document_count"] for c in before["collections"] if c["slug"] == "default-inbox"
    )

    files = {"file": ("counted.txt", b"abc", "text/plain")}
    ir = intake_api_client.post("/api/v1/documents", files=files)
    assert ir.status_code == 200

    after = intake_api_client.get("/api/v1/collections").json()
    default_after = next(
        c["document_count"] for c in after["collections"] if c["slug"] == "default-inbox"
    )
    assert default_after == default_before + 1


@pytest.mark.integration
def test_scaffold_pipeline_persists_run_events_and_completes_document(
    intake_api_client,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DATABASE_URL", database_url)
    from app.core.config import reset_settings_cache
    from app.db.session import get_session_factory, reset_engine
    from app.services.opensearch_document_index import reset_fake_opensearch_index
    from app.services.pipeline_run_service import execute_scaffold_pipeline

    reset_fake_opensearch_index()
    reset_settings_cache()
    reset_engine()

    files = {"file": ("pipe.txt", b"data", "text/plain")}
    r = intake_api_client.post("/api/v1/documents", files=files)
    assert r.status_code == 200, r.text
    did = r.json()["document_id"]

    sess = get_session_factory()()
    try:
        execute_scaffold_pipeline(sess, uuid.UUID(did), "job-integration-test")
        sess.commit()
    finally:
        sess.close()

    with psycopg.connect(database_url) as conn:
        st = conn.execute(
            "SELECT status FROM documents WHERE id = %s::uuid",
            (did,),
        ).fetchone()[0]
        assert st == "completed"

        pr = conn.execute(
            "SELECT status, stage FROM pipeline_runs WHERE document_id = %s::uuid "
            "ORDER BY created_at DESC LIMIT 1",
            (did,),
        ).fetchone()
        assert pr is not None
        assert pr[0] == "succeeded"
        assert pr[1] == "finalize"

        ev_count = conn.execute(
            """
            SELECT COUNT(*) FROM pipeline_events pe
            INNER JOIN pipeline_runs pr ON pr.id = pe.pipeline_run_id
            WHERE pr.document_id = %s::uuid
            """,
            (did,),
        ).fetchone()[0]
        # pipeline_started + 6×pipeline_stage + substages (ingest, extract, enrich, score, index)
        assert ev_count == 12

        row = conn.execute(
            "SELECT body_text, extract_artifact_key FROM documents WHERE id = %s::uuid",
            (did,),
        ).fetchone()
        assert row[0] == "data"
        assert row[1] == f"artifacts/{did}/extracted.txt"


@pytest.mark.integration
def test_pipeline_enqueues_score_job_when_configured(
    intake_api_client,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ENQUEUE_SCORE_AFTER_PIPELINE", "true")
    import asyncio

    from app.core.config import reset_settings_cache
    from app.db.session import get_session_factory, reset_engine
    from app.services.opensearch_document_index import reset_fake_opensearch_index
    from app.services.pipeline_run_service import execute_scaffold_pipeline
    from app.services.queue_backend import close_job_queue, get_memory_queue

    reset_fake_opensearch_index()
    reset_settings_cache()
    reset_engine()
    asyncio.run(close_job_queue())

    files = {"file": ("score-enqueue.txt", b"queued", "text/plain")}
    r = intake_api_client.post("/api/v1/documents", files=files)
    assert r.status_code == 200, r.text
    did = r.json()["document_id"]

    sess = get_session_factory()()
    try:
        execute_scaffold_pipeline(sess, uuid.UUID(did), "job-score-enqueue-test")
        sess.commit()
    finally:
        sess.close()

    q = get_memory_queue()
    score_hits = [j for j in q.jobs if j[1] == "score_document" and j[2] == did]
    assert len(score_hits) == 1


@pytest.mark.integration
def test_score_stub_worker_inserts_document_score_row(
    intake_api_client,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DATABASE_URL", database_url)
    from app.core.config import reset_settings_cache
    from app.db.session import get_session_factory, reset_engine
    from app.services.opensearch_document_index import reset_fake_opensearch_index
    from app.services.pipeline_run_service import execute_scaffold_pipeline
    from app.services.score_document_worker import run_score_document_sync

    reset_fake_opensearch_index()
    reset_settings_cache()
    reset_engine()

    files = {"file": ("score-stub.txt", b"x", "text/plain")}
    r = intake_api_client.post("/api/v1/documents", files=files)
    assert r.status_code == 200, r.text
    did = r.json()["document_id"]

    sess = get_session_factory()()
    try:
        execute_scaffold_pipeline(sess, uuid.UUID(did), "job-score-stub-test")
        sess.commit()
    finally:
        sess.close()

    run_score_document_sync(did)

    with psycopg.connect(database_url) as conn:
        n = conn.execute(
            """
            SELECT COUNT(*) FROM document_scores
            WHERE document_id = %s::uuid AND scorer_name = 'verifiedsignal_stub'
            """,
            (did,),
        ).fetchone()[0]
    assert n >= 1
