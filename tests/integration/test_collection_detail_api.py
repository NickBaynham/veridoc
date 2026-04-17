"""Integration: collection workspace detail and document directory APIs."""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.integration
def test_get_collection_detail_default_inbox(intake_api_client) -> None:
    lst = intake_api_client.get("/api/v1/collections").json()
    inbox = next(c for c in lst["collections"] if c["slug"] == "default-inbox")
    cid = inbox["id"]
    r = intake_api_client.get(f"/api/v1/collections/{cid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == cid
    assert d["name"] == "Default Inbox"
    assert d["slug"] == "default-inbox"
    assert "document_count" in d
    assert d["description"] is None
    assert "status_breakdown" in d
    assert isinstance(d["status_breakdown"], dict)


@pytest.mark.integration
def test_get_collection_detail_unknown_returns_404(intake_api_client) -> None:
    missing = uuid.uuid4()
    r = intake_api_client.get(f"/api/v1/collections/{missing}")
    assert r.status_code == 404


@pytest.mark.integration
def test_list_collection_documents_pagination_and_search(intake_api_client) -> None:
    lst = intake_api_client.get("/api/v1/collections").json()
    inbox = next(c for c in lst["collections"] if c["slug"] == "default-inbox")
    cid = inbox["id"]

    probe = intake_api_client.get(f"/api/v1/collections/{cid}/documents", params={"limit": 1})
    assert probe.status_code == 200
    assert probe.json()["total"] >= 0
    assert isinstance(probe.json()["items"], list)

    intake_api_client.post(
        "/api/v1/documents",
        files={"file": ("alpha_unique_xyz.txt", b"hello", "text/plain")},
    )
    intake_api_client.post(
        "/api/v1/documents",
        files={"file": ("beta_other.txt", b"world", "text/plain")},
    )

    r = intake_api_client.get(f"/api/v1/collections/{cid}/documents", params={"limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["collection_id"] == cid
    assert data["total"] >= 2
    titles = {item["title"] for item in data["items"]}
    assert any("alpha_unique_xyz" in (t or "") for t in titles)

    sr = intake_api_client.get(
        f"/api/v1/collections/{cid}/documents",
        params={"q": "alpha_unique"},
    )
    assert sr.status_code == 200
    sdata = sr.json()
    assert sdata["total"] >= 1
    for i in sdata["items"]:
        blob = f"{i.get('title') or ''} {i.get('original_filename') or ''}"
        assert "alpha_unique" in blob


@pytest.mark.integration
def test_list_collection_documents_sort_and_invalid_sort(intake_api_client) -> None:
    lst = intake_api_client.get("/api/v1/collections").json()
    cid = next(c for c in lst["collections"] if c["slug"] == "default-inbox")["id"]

    bad = intake_api_client.get(
        f"/api/v1/collections/{cid}/documents",
        params={"sort": "not_a_real_sort"},
    )
    assert bad.status_code == 400

    ok = intake_api_client.get(
        f"/api/v1/collections/{cid}/documents",
        params={"sort": "name_asc", "limit": 5},
    )
    assert ok.status_code == 200


@pytest.mark.integration
def test_list_collection_documents_filter_status(intake_api_client) -> None:
    lst = intake_api_client.get("/api/v1/collections").json()
    cid = next(c for c in lst["collections"] if c["slug"] == "default-inbox")["id"]
    r = intake_api_client.get(
        f"/api/v1/collections/{cid}/documents",
        params={"status": "queued", "limit": 50},
    )
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "queued"


@pytest.mark.integration
def test_list_collection_documents_unknown_collection(intake_api_client) -> None:
    r = intake_api_client.get(f"/api/v1/collections/{uuid.uuid4()}/documents")
    assert r.status_code == 404


@pytest.mark.integration
def test_get_delete_document_still_works(intake_api_client) -> None:
    lst = intake_api_client.get("/api/v1/collections").json()
    cid = next(c for c in lst["collections"] if c["slug"] == "default-inbox")["id"]
    up = intake_api_client.post(
        "/api/v1/documents",
        files={"file": ("to_remove.txt", b"x", "text/plain")},
    )
    assert up.status_code == 200
    did = up.json()["document_id"]

    one = intake_api_client.get(f"/api/v1/documents/{did}")
    assert one.status_code == 200
    assert one.json()["collection_id"] == cid

    rm = intake_api_client.delete(f"/api/v1/documents/{did}")
    assert rm.status_code == 204
    gone = intake_api_client.get(f"/api/v1/documents/{did}")
    assert gone.status_code == 404


@pytest.mark.integration
def test_move_document_between_collections(intake_api_client, database_url: str) -> None:
    """Invalid target returns 403; happy path mirrors test_document_collection_transfer seeding."""
    import psycopg

    sub = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    uid = uuid.UUID(sub)
    org_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO users (id, email, display_name, external_sub)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
              email = EXCLUDED.email,
              display_name = EXCLUDED.display_name,
              external_sub = EXCLUDED.external_sub
            """,
            (uid, "detail-move@verifiedsignal.test", "Detail Move", sub),
        )
        conn.execute(
            """
            INSERT INTO organization_members (organization_id, user_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT DO NOTHING
            """,
            (org_id, uid),
        )
        conn.commit()

    cr = intake_api_client.post(
        "/api/v1/collections",
        json={"name": "Move Target Workspace", "organization_id": str(org_id)},
    )
    assert cr.status_code == 201, cr.text
    target_id = cr.json()["id"]

    up = intake_api_client.post(
        "/api/v1/documents",
        files={"file": ("movable.txt", b"z", "text/plain")},
    )
    assert up.status_code == 200
    did = up.json()["document_id"]

    bad = intake_api_client.post(
        f"/api/v1/documents/{did}/move",
        json={"collection_id": str(uuid.uuid4())},
    )
    assert bad.status_code == 403

    mv = intake_api_client.post(
        f"/api/v1/documents/{did}/move",
        json={"collection_id": target_id},
    )
    assert mv.status_code == 200, mv.text
    assert mv.json()["collection_id"] == target_id

    intake_api_client.delete(f"/api/v1/documents/{did}")
    intake_api_client.delete(f"/api/v1/collections/{target_id}")
