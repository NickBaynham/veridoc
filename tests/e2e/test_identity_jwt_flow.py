"""
E2E-style flow: real JWT + Postgres + multiple HTTP steps (requires DATABASE_URL + migrations).
"""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.e2e
@pytest.mark.api
@pytest.mark.integration
def test_identity_jwt_login_then_collections_then_me(jwt_integration_client) -> None:
    """Simulates post-login API usage: collections list and profile reflect provisioned tenant."""
    client, make_token = jwt_integration_client
    sub = str(uuid.uuid4())
    email = "e2e-flow@example.com"
    token = make_token(sub=sub, email=email)
    headers = {"Authorization": f"Bearer {token}"}

    col = client.get("/api/v1/collections", headers=headers)
    assert col.status_code == 200
    assert col.json()["collections"]

    sync = client.post("/auth/sync-identity", headers=headers)
    assert sync.status_code == 200

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["user_id"] == sub
    assert body["email"] == email
    assert body["database_user_id"] == sync.json()["database_user_id"]
