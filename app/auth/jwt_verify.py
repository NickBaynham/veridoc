"""Decode Supabase access tokens using HS256 (local) or JWKS RS256 (hosted)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.jwk import construct

from app.auth.claims import AccessTokenClaims
from app.core.config import Settings


@lru_cache(maxsize=4)
def _jwks_document(url: str) -> dict:
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _decode_access_token_payload(token: str, settings: Settings) -> dict[str, Any]:
    jwks_url = settings.supabase_jwks_url.strip()
    if jwks_url:
        jwks = _jwks_document(jwks_url)
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        keys = jwks.get("keys", [])
        key_dict = next((k for k in keys if k.get("kid") == kid), None)
        if key_dict is None:
            raise JWTError("no matching JWK for kid")
        key = construct(key_dict)
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.jwt_audience,
            options={"verify_aud": True},
        )
    secret = settings.supabase_jwt_secret.strip()
    if not secret:
        raise JWTError("SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL must be set")
    return jwt.decode(
        token,
        secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        options={"verify_aud": True},
    )


def _display_name_from_payload(payload: dict[str, Any]) -> str | None:
    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    meta = payload.get("user_metadata")
    if isinstance(meta, dict):
        for key in ("full_name", "name", "display_name"):
            v = meta.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def decode_access_token_claims(token: str, settings: Settings) -> AccessTokenClaims:
    """
    Verify JWT and return claims used for tenancy (sub, email, display name hints).
    """
    payload = _decode_access_token_payload(token, settings)
    sub = payload.get("sub")
    if not sub:
        raise JWTError("missing sub claim")
    email_raw = payload.get("email")
    email: str | None = None
    if isinstance(email_raw, str) and email_raw.strip():
        email = email_raw.strip()
    return AccessTokenClaims(
        sub=str(sub),
        email=email,
        display_name=_display_name_from_payload(payload),
    )


def decode_access_token_sub(token: str, settings: Settings) -> str:
    """
    Verify JWT and return Auth user id (`sub`).
    JWKS URL set → RS256 + remote keys; otherwise HS256 + SUPABASE_JWT_SECRET.
    """
    return decode_access_token_claims(token, settings).sub
