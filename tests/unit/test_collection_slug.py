"""Unit tests for collection slug helpers."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.services.collection_slug import collection_slug_base, next_unique_collection_slug


def test_collection_slug_base_trims_and_lowercases() -> None:
    assert collection_slug_base("  My Team  ") == "my-team"


def test_collection_slug_base_empty_becomes_collection() -> None:
    assert collection_slug_base("   !!! ") == "collection"


def test_next_unique_collection_slug_collisions() -> None:
    session = MagicMock()
    # First candidate "foo" exists; "foo-2" is free
    session.scalar.side_effect = [uuid.uuid4(), None]
    org = uuid.uuid4()
    assert next_unique_collection_slug(session, org, "foo") == "foo-2"


def test_next_unique_collection_slug_ignores_self() -> None:
    session = MagicMock()
    session.scalar.return_value = None
    org = uuid.uuid4()
    cid = uuid.uuid4()
    assert next_unique_collection_slug(session, org, "foo", ignore_collection_id=cid) == "foo"
