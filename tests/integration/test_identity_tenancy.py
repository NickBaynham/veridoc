"""Postgres-backed identity provisioning (Supabase JWT sub → users + org + inbox)."""

from __future__ import annotations

import uuid

import pytest
from jose import jwt


@pytest.mark.integration
def test_first_bearer_request_creates_personal_collection(
    jwt_integration_client,
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, make_token = jwt_integration_client
    sub = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {make_token(sub=sub, email='tenant@example.com')}"}

    r = client.get("/api/v1/collections", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["collections"]) >= 1
    slugs = {c["slug"] for c in data["collections"]}
    assert "inbox" in slugs

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, external_sub FROM users WHERE external_sub = %s",
            (sub,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[1] == "tenant@example.com"

        cur.execute(
            """
            SELECT COUNT(*) FROM organization_members om
            JOIN users u ON u.id = om.user_id
            WHERE u.external_sub = %s AND om.role = 'owner'
            """,
            (sub,),
        )
        assert cur.fetchone()[0] == 1


@pytest.mark.integration
def test_strict_tenancy_no_fallback_without_user_or_provision(
    jwt_integration_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY", "false")
    monkeypatch.setenv("VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK", "false")
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    client, make_token = jwt_integration_client
    sub = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {make_token(sub=sub)}"}
    r = client.get("/api/v1/collections", headers=headers)
    assert r.status_code == 200
    assert r.json()["collections"] == []


@pytest.mark.integration
def test_auth_sync_identity_matches_first_request_provision(
    jwt_integration_client,
) -> None:
    client, make_token = jwt_integration_client
    sub = str(uuid.uuid4())
    token = make_token(sub=sub, email="sync@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    s1 = client.post("/auth/sync-identity", headers=headers)
    assert s1.status_code == 200
    body1 = s1.json()
    assert body1["database_user_id"]
    assert len(body1["collection_ids"]) >= 1

    s2 = client.post("/auth/sync-identity", headers=headers)
    assert s2.status_code == 200
    assert s2.json()["database_user_id"] == body1["database_user_id"]

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["database_user_id"] == body1["database_user_id"]
    assert me.json()["email"] == "sync@example.com"


@pytest.mark.integration
def test_users_me_returns_claims_and_database_user_id(jwt_integration_client) -> None:
    """GET /users/me includes JWT `user_id` and linked Postgres `database_user_id`."""
    client, make_token = jwt_integration_client
    sub = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {make_token(sub=sub)}"}
    r = client.get("/api/v1/users/me", headers=headers)
    assert r.status_code == 200
    j = r.json()
    assert j["user_id"] == sub
    assert j["database_user_id"] is not None


@pytest.mark.integration
def test_sync_identity_rejects_invalid_jwt(jwt_integration_client) -> None:
    client, _make = jwt_integration_client
    bad = jwt.encode(
        {"sub": "x", "aud": "wrong"},
        "jwt-integration-test-secret-must-be-long-enough-for-hs256!!",
        algorithm="HS256",
    )
    r = client.post(
        "/auth/sync-identity",
        headers={"Authorization": f"Bearer {bad}"},
    )
    assert r.status_code == 401
