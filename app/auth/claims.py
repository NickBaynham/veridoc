"""Verified claims from a Supabase access token (after signature + audience checks)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Subset of JWT payload used for Postgres identity and provisioning."""

    sub: str
    email: str | None
    display_name: str | None
