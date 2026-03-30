"""Unit tests: object key helpers and in-memory storage adapter."""

from __future__ import annotations

import uuid

import pytest
from app.services.storage_service import (
    InMemoryObjectStorage,
    build_extract_artifact_key,
    build_raw_object_key,
    sanitize_filename,
)


@pytest.mark.unit
def test_sanitize_filename_strips_path_and_chars():
    assert sanitize_filename("dir/sub/file_name!.txt") == "file_name_.txt"
    assert sanitize_filename("  ") == "unnamed"


@pytest.mark.unit
def test_build_raw_object_key_shape():
    did = uuid.UUID("00000000-0000-4000-8000-000000000099")
    key = build_raw_object_key(did, "My File (1).pdf")
    assert key.startswith(f"raw/{did}/")
    assert key.endswith(".pdf")


@pytest.mark.unit
def test_build_extract_artifact_key_shape():
    did = uuid.UUID("00000000-0000-4000-8000-000000000099")
    assert build_extract_artifact_key(did) == f"artifacts/{did}/extracted.txt"


@pytest.mark.unit
def test_in_memory_object_exists():
    store = InMemoryObjectStorage(bucket="b1")
    assert store.object_exists("nope") is False
    store.upload_bytes("k", b"x", None)
    assert store.object_exists("k") is True


@pytest.mark.unit
def test_in_memory_storage_roundtrip():
    store = InMemoryObjectStorage(bucket="b1")
    store.ensure_bucket()
    store.upload_bytes("raw/x/y.txt", b"abc", "text/plain")
    assert store.objects["raw/x/y.txt"] == b"abc"
    assert store.bucket == "b1"


@pytest.mark.unit
def test_in_memory_get_bytes_roundtrip():
    store = InMemoryObjectStorage(bucket="b1")
    store.upload_bytes("k", b"payload", None)
    assert store.get_bytes("k") == b"payload"


@pytest.mark.unit
def test_in_memory_get_bytes_missing_raises():
    store = InMemoryObjectStorage(bucket="b1")
    with pytest.raises(KeyError):
        store.get_bytes("missing")


@pytest.mark.unit
def test_in_memory_delete_object_idempotent():
    store = InMemoryObjectStorage(bucket="b1")
    store.upload_bytes("k", b"x", None)
    store.delete_object("k")
    assert "k" not in store.objects
    store.delete_object("k")
