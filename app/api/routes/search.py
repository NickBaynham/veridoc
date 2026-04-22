"""Search API: full-text + metadata filters over OpenSearch (or in-memory fake when configured)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.dependencies import get_optional_current_user_sub
from app.schemas.search import SearchResponse
from app.services.search_service import search_documents

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    db: Session = Depends(get_db),
    auth_sub: str | None = Depends(get_optional_current_user_sub),
    q: str = Query("", min_length=0, max_length=2000),
    limit: int = Query(10, ge=1, le=100),
    collection_id: uuid.UUID | None = Query(
        default=None,
        description="Narrow to one collection (must be accessible when authenticated).",
    ),
    content_type: str | None = Query(default=None, max_length=256),
    status: str | None = Query(default=None, max_length=32),
    ingest_source: str | None = Query(
        default=None,
        description="Filter by primary ingest path: upload | url",
    ),
    tags: Annotated[
        list[str] | None,
        Query(description="Repeat for AND semantics, e.g. tag=a&tag=b"),
    ] = None,
    include_facets: bool = Query(
        default=False,
        description="Include facet bucket counts (ingest_source, status, content_type, tags).",
    ),
    semantic_weight: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Re-rank keyword hits using deterministic pseudo-embeddings (no external model). "
            "Ignored when q is empty."
        ),
    ),
) -> SearchResponse:
    raw = await search_documents(
        db,
        auth_sub,
        q,
        limit=limit,
        collection_id=collection_id,
        content_type=content_type,
        status=status,
        ingest_source=ingest_source,
        tags=tags,
        include_facets=include_facets,
        semantic_weight=semantic_weight,
    )
    return SearchResponse(**raw)
