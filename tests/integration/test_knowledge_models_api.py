"""Integration: knowledge model APIs (requires Postgres migrations through 006)."""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.integration
def test_knowledge_models_crud_and_assets(intake_api_client) -> None:
    lst = intake_api_client.get("/api/v1/collections").json()
    inbox = next(c for c in lst["collections"] if c["slug"] == "default-inbox")
    cid = inbox["id"]

    up1 = intake_api_client.post(
        "/api/v1/documents",
        files={"file": ("km_doc_a.txt", b"alpha content for model", "text/plain")},
        data={"collection_id": cid},
    )
    assert up1.status_code == 200, up1.text
    did_a = up1.json()["document_id"]
    up2 = intake_api_client.post(
        "/api/v1/documents",
        files={"file": ("km_doc_b.txt", b"beta second file", "text/plain")},
        data={"collection_id": cid},
    )
    assert up2.status_code == 200, up2.text
    did_b = up2.json()["document_id"]

    empty = intake_api_client.get(f"/api/v1/collections/{cid}/models")
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    create = intake_api_client.post(
        f"/api/v1/collections/{cid}/models",
        json={
            "name": "Q1 Summary",
            "description": "Test model",
            "model_type": "summary",
            "selected_document_ids": [did_a, did_b],
            "build_profile": {"note": "integration"},
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["version"]["build_status"] == "completed"
    assert body["knowledge_model"]["name"] == "Q1 Summary"
    mid = body["knowledge_model"]["id"]
    vid = body["version"]["id"]

    listed = intake_api_client.get(f"/api/v1/collections/{cid}/models")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    detail = intake_api_client.get(f"/api/v1/models/{mid}")
    assert detail.status_code == 200
    dj = detail.json()
    assert dj["summary_json"] is not None
    assert dj["summary_json"].get("kind") == "summary_v1"

    vers = intake_api_client.get(f"/api/v1/models/{mid}/versions")
    assert vers.status_code == 200
    assert len(vers.json()["items"]) == 1

    vd = intake_api_client.get(f"/api/v1/models/{mid}/versions/{vid}")
    assert vd.status_code == 200
    assert vd.json()["version_number"] == 1

    assets = intake_api_client.get(f"/api/v1/models/{mid}/versions/{vid}/assets")
    assert assets.status_code == 200
    ad = assets.json()
    assert len(ad["items"]) == 2
    doc_ids = {x["document_id"] for x in ad["items"]}
    assert doc_ids == {did_a, did_b}


@pytest.mark.integration
def test_create_model_rejects_foreign_document(intake_api_client) -> None:
    lst = intake_api_client.get("/api/v1/collections").json()
    inbox = next(c for c in lst["collections"] if c["slug"] == "default-inbox")
    cid = inbox["id"]

    bad = intake_api_client.post(
        f"/api/v1/collections/{cid}/models",
        json={
            "name": "Bad",
            "model_type": "summary",
            "selected_document_ids": [str(uuid.uuid4())],
        },
    )
    assert bad.status_code == 400
