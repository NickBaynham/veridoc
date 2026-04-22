"""
Deterministic pseudo-embeddings for semantic-style ranking (no external model).

Same input text yields the same unit-length vector so search re-ranking is reproducible.
"""

from __future__ import annotations

import hashlib
import math


def deterministic_text_embedding(text: str | None, *, dim: int = 64) -> list[float]:
    if not text or not str(text).strip():
        return [0.0] * dim
    t = str(text).strip().lower()[:8000]
    vec = [0.0] * dim
    for i in range(dim):
        h = hashlib.sha256(f"{i}:{t}".encode()).digest()
        val = int.from_bytes(h[:4], "little") / (2**32) * 2.0 - 1.0
        vec[i] = val
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    return float(sum(x * y for x, y in zip(a, b, strict=True)))
