"""Search API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchResponse(BaseModel):
    query: str
    limit: int
    semantic_weight: float = Field(
        default=0.0,
        description="Blend with deterministic pseudo-embeddings (0=keyword only, 1=vector only).",
    )
    hits: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    index_status: str
    message: str | None = None
    facets: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Facet buckets when include_facets=true "
            "(ingest_source, status, content_type, tags)."
        ),
    )
