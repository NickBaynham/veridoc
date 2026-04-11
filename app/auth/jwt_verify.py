"""Decode Supabase access tokens: HS* + shared secret, or asymmetric via JWKS (RS256/ES256/…)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.jwk import construct

from app.auth.claims import AccessTokenClaims
from app.core.config import Settings

_ASYMMETRIC_ALGS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"})


@lru_cache(maxsize=8)
def _jwks_document(url: str) -> dict:
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _jwks_url_for_settings(settings: Settings) -> str | None:
    explicit = settings.supabase_jwks_url.strip()
    if explicit:
        return explicit
    base = settings.supabase_url.strip().rstrip("/")
    if not base:
        return None
    return f"{base}/auth/v1/.well-known/jwks.json"


def _decode_access_token_payload(token: str, settings: Settings) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise
    alg = (header.get("alg") or "HS256").upper()

    if alg in ("HS256", "HS384", "HS512"):
        secret = settings.supabase_jwt_secret.strip()
        if not secret:
            raise JWTError(
                "SUPABASE_JWT_SECRET must be set for HS256 access tokens "
                "(or use asymmetric tokens verified via JWKS)"
            )
        return jwt.decode(
            token,
            secret,
            algorithms=[alg],
            audience=settings.jwt_audience,
            options={"verify_aud": True},
        )

    if alg not in _ASYMMETRIC_ALGS:
        raise JWTError(f"unsupported JWT alg for access token: {alg}")

    jwks_url = _jwks_url_for_settings(settings)
    if not jwks_url:
        raise JWTError(
            "asymmetric JWT (RS256/ES256/…) requires SUPABASE_URL or SUPABASE_JWKS_URL "
            "so JWKS can be fetched"
        )
    jwks = _jwks_document(jwks_url)
    kid = header.get("kid")
    keys = jwks.get("keys", [])
    key_dict = next((k for k in keys if k.get("kid") == kid), None)
    if key_dict is None:
        raise JWTError("no matching JWK for kid")
    key = construct(key_dict)
    return jwt.decode(
        token,
        key,
        algorithms=list(_ASYMMETRIC_ALGS),
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
    HS* tokens use SUPABASE_JWT_SECRET; RS256/ES256/… use JWKS from SUPABASE_JWKS_URL or
    `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`.
    """
    return decode_access_token_claims(token, settings).sub
