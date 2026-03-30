"""Session auth routes with Supabase client mocked (no real network)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.auth.supabase_service import reset_supabase_service_client
from app.core.config import reset_settings_cache
from app.main import create_app
from fastapi.testclient import TestClient
from jose import jwt
from supabase_auth.errors import AuthApiError, AuthInvalidCredentialsError

_SUPABASE_ENV = {
    "SUPABASE_URL": "http://localhost:54321",
    "SUPABASE_ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.test-service-key",
    "SUPABASE_JWT_SECRET": "super-long-test-secret-for-hs256-verification!!",
    "JWT_ALGORITHM": "HS256",
    "JWT_AUDIENCE": "authenticated",
}


@pytest.fixture
def supabase_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, val in _SUPABASE_ENV.items():
        monkeypatch.setenv(key, val)
    reset_settings_cache()
    reset_supabase_service_client()
    yield
    reset_supabase_service_client()
    reset_settings_cache()


def _mock_client(monkeypatch: pytest.MonkeyPatch, mock: MagicMock) -> None:
    monkeypatch.setattr(
        "app.api.routes.session_auth.get_supabase_service_client",
        lambda: mock,
    )


def test_signup_ok(supabase_auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock()
    mock.auth.sign_up.return_value = MagicMock(session=None, user=MagicMock())
    _mock_client(monkeypatch, mock)
    with TestClient(create_app()) as client:
        r = client.post(
            "/auth/signup",
            json={"email": "new@example.com", "password": "password123"},
        )
    assert r.status_code == 200
    assert r.json()["message"] == "Check your email to confirm your account"
    mock.auth.sign_up.assert_called_once()


def test_signup_duplicate_email(supabase_auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock()
    mock.auth.sign_up.side_effect = AuthApiError("duplicate", 400, "email_exists")
    _mock_client(monkeypatch, mock)
    with TestClient(create_app()) as client:
        r = client.post(
            "/auth/signup",
            json={"email": "dup@example.com", "password": "password123"},
        )
    assert r.status_code == 400


def test_login_ok_sets_cookie(supabase_auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=3600,
    )
    mock = MagicMock()
    mock.auth.sign_in_with_password.return_value = MagicMock(session=session)
    _mock_client(monkeypatch, mock)
    with TestClient(create_app()) as client:
        r = client.post(
            "/auth/login",
            json={"email": "u@example.com", "password": "password123"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "access-token"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert r.cookies.get("vs_refresh_token") == "refresh-token"


def test_login_invalid_password(supabase_auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock()
    mock.auth.sign_in_with_password.side_effect = AuthInvalidCredentialsError("nope")
    _mock_client(monkeypatch, mock)
    with TestClient(create_app()) as client:
        r = client.post(
            "/auth/login",
            json={"email": "u@example.com", "password": "wrong"},
        )
    assert r.status_code == 401


def test_refresh_ok(supabase_auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    new_session = MagicMock(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_in=3600,
    )
    mock = MagicMock()
    mock.auth.refresh_session.return_value = MagicMock(session=new_session)
    _mock_client(monkeypatch, mock)
    with TestClient(create_app()) as client:
        r = client.post("/auth/refresh", cookies={"vs_refresh_token": "old-refresh"})
    assert r.status_code == 200
    assert r.json()["access_token"] == "new-access"
    assert r.cookies.get("vs_refresh_token") == "new-refresh"


def test_refresh_missing_cookie(supabase_auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock()
    _mock_client(monkeypatch, mock)
    with TestClient(create_app()) as client:
        r = client.post("/auth/refresh")
    assert r.status_code == 401


def test_logout_clears_cookie(supabase_auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock()
    mock.auth.refresh_session.return_value = MagicMock(
        session=MagicMock(access_token="a", refresh_token="r"),
    )
    _mock_client(monkeypatch, mock)
    with TestClient(create_app()) as client:
        r = client.post("/auth/logout", cookies={"vs_refresh_token": "r"})
    assert r.status_code == 204


def test_documents_without_token_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "")
    monkeypatch.setenv("SUPABASE_JWKS_URL", "")
    reset_settings_cache()
    with TestClient(create_app()) as client:
        r = client.get("/api/v1/documents")
    assert r.status_code == 401
    reset_settings_cache()


def test_documents_with_valid_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = _SUPABASE_ENV["SUPABASE_JWT_SECRET"]
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_AUDIENCE", "authenticated")
    reset_settings_cache()

    def _fake_get_db():
        yield MagicMock()

    monkeypatch.setattr("app.auth.dependencies.get_db", _fake_get_db)
    monkeypatch.setattr("app.api.routes.documents.get_db", _fake_get_db)
    monkeypatch.setattr(
        "app.auth.dependencies.ensure_personal_tenant_for_claims",
        lambda *_a, **_k: (None, False),
    )

    def _fake_list(*_a, **_k):
        return ([], 0)

    monkeypatch.setattr("app.api.routes.documents.list_documents_for_user", _fake_list)

    token = jwt.encode(
        {"sub": "user-xyz", "aud": "authenticated"},
        secret,
        algorithm="HS256",
    )
    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "user-xyz"
    assert body["items"] == []
    assert body["total"] == 0
    reset_settings_cache()
