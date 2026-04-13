"""effective_supabase_url_for_server rewrites loopback when /.dockerenv is present."""

from __future__ import annotations

from app.core.config import Settings, effective_supabase_url_for_server


def test_no_rewrite_when_not_in_container(monkeypatch):
    monkeypatch.setattr("app.core.config.os.path.exists", lambda p: False)
    s = Settings.model_construct(supabase_url="http://127.0.0.1:54321")
    assert effective_supabase_url_for_server(s) == "http://127.0.0.1:54321"


def test_rewrite_loopback_when_in_container(monkeypatch):
    monkeypatch.setattr("app.core.config.os.path.exists", lambda p: str(p) == "/.dockerenv")
    s = Settings.model_construct(supabase_url="http://127.0.0.1:54321")
    assert effective_supabase_url_for_server(s) == "http://host.docker.internal:54321"


def test_rewrite_localhost_with_port(monkeypatch):
    monkeypatch.setattr("app.core.config.os.path.exists", lambda p: str(p) == "/.dockerenv")
    s = Settings.model_construct(supabase_url="http://localhost:54321/auth/v1")
    assert effective_supabase_url_for_server(s) == "http://host.docker.internal:54321/auth/v1"


def test_hosted_url_unchanged_in_container(monkeypatch):
    monkeypatch.setattr("app.core.config.os.path.exists", lambda p: str(p) == "/.dockerenv")
    url = "https://abcdefgh.supabase.co"
    s = Settings.model_construct(supabase_url=url)
    assert effective_supabase_url_for_server(s) == url


def test_host_docker_internal_unchanged_in_container(monkeypatch):
    monkeypatch.setattr("app.core.config.os.path.exists", lambda p: str(p) == "/.dockerenv")
    s = Settings.model_construct(supabase_url="http://host.docker.internal:54321")
    assert effective_supabase_url_for_server(s) == "http://host.docker.internal:54321"
