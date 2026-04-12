"""Integration: move and copy documents between accessible collections."""

from __future__ import annotations

import io
import uuid

import psycopg
import pytest

INBOX = uuid.UUID("00000000-0000-4000-8000-000000000002")
ORG = uuid.UUID("00000000-0000-4000-8000-000000000001")


@pytest.mark.integration
def test_move_and_copy_document_between_collections(intake_api_client, database_url: str) -> None:
    sub = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    uid = uuid.UUID(sub)

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
            (uid, "e2e-transfer@verifiedsignal.test", "E2E Transfer", sub),
        )
        conn.execute(
            """
            INSERT INTO organization_members (organization_id, user_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT DO NOTHING
            """,
            (ORG, uid),
        )
        conn.commit()

    r_col = intake_api_client.post(
        "/api/v1/collections",
        json={"name": "Transfer Target Bin", "organization_id": str(ORG)},
    )
    assert r_col.status_code == 201, r_col.text
    target_col = uuid.UUID(r_col.json()["id"])

    files = {"file": ("xfer.txt", io.BytesIO(b"hello transfer"), "text/plain")}
    data = {"collection_id": str(INBOX)}
    up = intake_api_client.post("/api/v1/documents", files=files, data=data)
    assert up.status_code == 200, up.text
    doc_id = uuid.UUID(up.json()["document_id"])

    mv = intake_api_client.post(
        f"/api/v1/documents/{doc_id}/move",
        json={"collection_id": str(target_col)},
    )
    assert mv.status_code == 200, mv.text
    assert mv.json()["collection_id"] == str(target_col)

    one = intake_api_client.get(f"/api/v1/documents/{doc_id}")
    assert one.status_code == 200
    assert one.json()["collection_id"] == str(target_col)
    orig_storage = one.json()["storage_key"]

    cp = intake_api_client.post(
        f"/api/v1/documents/{doc_id}/copy",
        json={"collection_id": str(INBOX)},
    )
    assert cp.status_code == 201, cp.text
    copy_id = uuid.UUID(cp.json()["id"])
    assert copy_id != doc_id
    assert cp.json()["collection_id"] == str(INBOX)

    c1 = intake_api_client.get(f"/api/v1/documents/{copy_id}")
    assert c1.status_code == 200
    assert c1.json()["collection_id"] == str(INBOX)

    rm_copy = intake_api_client.delete(f"/api/v1/documents/{copy_id}")
    assert rm_copy.status_code == 204, rm_copy.text

    still = intake_api_client.get(f"/api/v1/documents/{doc_id}")
    assert still.status_code == 200
    assert still.json()["storage_key"] == orig_storage

    rm_orig = intake_api_client.delete(f"/api/v1/documents/{doc_id}")
    assert rm_orig.status_code == 204

    gone = intake_api_client.get(f"/api/v1/documents/{doc_id}")
    assert gone.status_code == 404


@pytest.mark.integration
def test_move_rejects_inaccessible_target_collection(intake_api_client) -> None:
    files = {"file": ("t.txt", io.BytesIO(b"x"), "text/plain")}
    data = {"collection_id": str(INBOX)}
    up = intake_api_client.post("/api/v1/documents", files=files, data=data)
    assert up.status_code == 200, up.text
    did = up.json()["document_id"]
    bad_target = str(uuid.uuid4())
    r = intake_api_client.post(
        f"/api/v1/documents/{did}/move",
        json={"collection_id": bad_target},
    )
    assert r.status_code == 403, r.text
    intake_api_client.delete(f"/api/v1/documents/{did}")
