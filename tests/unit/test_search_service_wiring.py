"""Unit tests: fake OpenSearch index + async search_documents."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock

import pytest
from app.core.config import reset_settings_cache
from app.services import search_service as search_service_mod
from app.services.opensearch_document_index import index_document_sync, reset_fake_opensearch_index
from app.services.search_service import search_documents


@pytest.mark.unit
def test_search_documents_fake_keyword_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_FAKE_OPENSEARCH", "true")
    reset_settings_cache()
    reset_fake_opensearch_index()

    did = uuid.uuid4()
    cid = uuid.uuid4()
    index_document_sync(
        document_id=did,
        collection_id=cid,
        title="Report",
        body_text="quarterly revenue audit",
        status="completed",
    )

    monkeypatch.setattr(
        search_service_mod,
        "resolve_accessible_collection_ids",
        lambda *_a, **_kw: [cid],
    )

    db = MagicMock()
    out = asyncio.run(search_documents(db, "unit-test-sub", "revenue", limit=10))
    assert out["index_status"] == "fake"
    assert out["total"] == 1
    assert out["hits"][0]["document_id"] == str(did)
    assert "revenue" in (out["hits"][0].get("snippet") or "")


@pytest.mark.unit
def test_search_fake_filter_by_tag_and_metadata_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USE_FAKE_OPENSEARCH", "true")
    reset_settings_cache()
    reset_fake_opensearch_index()

    a = uuid.uuid4()
    b = uuid.uuid4()
    cid = uuid.uuid4()
    index_document_sync(
        document_id=a,
        collection_id=cid,
        title="One",
        body_text="alpha",
        status="completed",
        tags=["finance", "q1"],
        metadata_text="acme corp",
    )
    index_document_sync(
        document_id=b,
        collection_id=cid,
        title="Two",
        body_text="beta",
        status="completed",
        tags=["legal"],
        metadata_text="other",
    )

    monkeypatch.setattr(
        search_service_mod,
        "resolve_accessible_collection_ids",
        lambda *_a, **_kw: [cid],
    )

    db = MagicMock()
    out = asyncio.run(
        search_documents(
            db,
            "unit-test-sub",
            "",
            limit=10,
            tags=["finance"],
            ingest_source="upload",
        )
    )
    assert out["total"] == 1
    assert out["hits"][0]["document_id"] == str(a)

    out2 = asyncio.run(search_documents(db, "unit-test-sub", "acme", limit=10))
    assert out2["total"] == 1
    assert out2["hits"][0]["document_id"] == str(a)


@pytest.mark.unit
def test_search_documents_semantic_weight_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_FAKE_OPENSEARCH", "true")
    reset_settings_cache()
    reset_fake_opensearch_index()

    cid = uuid.uuid4()
    index_document_sync(
        document_id=uuid.uuid4(),
        collection_id=cid,
        title="Alpha topic",
        body_text="discussion of revenue growth",
        status="completed",
    )

    monkeypatch.setattr(
        search_service_mod,
        "resolve_accessible_collection_ids",
        lambda *_a, **_kw: [cid],
    )

    db = MagicMock()
    out = asyncio.run(
        search_documents(db, "unit-test-sub", "revenue", limit=5, semantic_weight=0.4)
    )
    assert out["semantic_weight"] == 0.4
    assert out["index_status"] == "fake"
