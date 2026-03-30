"""Unit tests for identity / tenancy helpers (no database)."""

from __future__ import annotations

import uuid

import pytest
from app.auth.claims import AccessTokenClaims
from app.services.identity_service import (
    normalized_email_for_claims,
    placeholder_email_for_sub,
    slug_fragment_from_sub,
)


@pytest.mark.unit
def test_slug_fragment_from_sub_uuid_like() -> None:
    s = "550E8400-E29B-41D4-A716-446655440000"
    assert slug_fragment_from_sub(s) == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.unit
def test_slug_fragment_from_sub_special_chars() -> None:
    assert slug_fragment_from_sub("auth0|abc|123") == "auth0-abc-123"


@pytest.mark.unit
def test_placeholder_email_stable() -> None:
    sub = "11111111-1111-1111-1111-111111111111"
    frag = slug_fragment_from_sub(sub)
    expected = f"{frag}@users.verifiedsignal.internal"
    assert placeholder_email_for_sub(sub) == expected


@pytest.mark.unit
def test_normalized_email_uses_claim() -> None:
    claims = AccessTokenClaims(
        sub=str(uuid.uuid4()),
        email="User@Example.COM",
        display_name=None,
    )
    assert normalized_email_for_claims(claims) == "user@example.com"


@pytest.mark.unit
def test_normalized_email_fallback_when_invalid() -> None:
    sub = "22222222-2222-2222-2222-222222222222"
    claims = AccessTokenClaims(sub=sub, email="not-an-email", display_name=None)
    assert normalized_email_for_claims(claims) == placeholder_email_for_sub(sub)
