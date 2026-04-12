"""Integration: create / rename / delete collections."""

from __future__ import annotations

import uuid

import psycopg
import pytest


@pytest.mark.integration
def test_create_patch_delete_collection(intake_api_client, database_url: str) -> None:
    """Caller must belong to the seeded local-dev org (integration fixture sub)."""
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
            (uid, "e2e-collections@verifiedsignal.test", "E2E Collections", sub),
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

    r = intake_api_client.post(
        "/api/v1/collections",
        json={"name": "Mutation Test Collection", "organization_id": str(org_id)},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    cid = body["id"]
    assert body["name"] == "Mutation Test Collection"
    assert body["slug"] == "mutation-test-collection"

    r2 = intake_api_client.patch(f"/api/v1/collections/{cid}", json={"name": "Renamed Coll"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["name"] == "Renamed Coll"
    assert r2.json()["slug"] == "renamed-coll"

    r3 = intake_api_client.delete(f"/api/v1/collections/{cid}")
    assert r3.status_code == 204, r3.text

    lst = intake_api_client.get("/api/v1/collections").json()
    ids = {c["id"] for c in lst["collections"]}
    assert cid not in ids


@pytest.mark.integration
def test_patch_delete_collection_unknown_returns_404(intake_api_client) -> None:
    missing = str(uuid.uuid4())
    pr = intake_api_client.patch(f"/api/v1/collections/{missing}", json={"name": "Nope"})
    assert pr.status_code == 404, pr.text

    dr = intake_api_client.delete(f"/api/v1/collections/{missing}")
    assert dr.status_code == 404, dr.text
