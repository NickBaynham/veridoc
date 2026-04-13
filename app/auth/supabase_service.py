"""Lazy Supabase client (service role) for auth router pass-through calls."""

from __future__ import annotations

from supabase import Client

from app.core.config import effective_supabase_url_for_server, get_settings

_client: Client | None = None


def get_supabase_service_client() -> Client:
    """Singleton GoTrue-capable client using the service role key."""
    global _client
    if _client is None:
        from supabase import create_client

        s = get_settings()
        base = effective_supabase_url_for_server(s)
        if not base or not s.supabase_service_role_key.strip():
            raise RuntimeError("Supabase URL and service role key are required")
        _client = create_client(base, s.supabase_service_role_key.strip())
    return _client


def reset_supabase_service_client() -> None:
    """Test hook."""
    global _client
    _client = None
