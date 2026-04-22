"""Unit tests: deterministic pseudo-embeddings."""

from __future__ import annotations

from app.services.text_embedding_stub import cosine_similarity, deterministic_text_embedding


def test_deterministic_embedding_stable() -> None:
    a = deterministic_text_embedding("hello world", dim=32)
    b = deterministic_text_embedding("hello world", dim=32)
    assert len(a) == 32
    assert a == b


def test_cosine_similarity_same_vector() -> None:
    v = deterministic_text_embedding("x", dim=16)
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-5
