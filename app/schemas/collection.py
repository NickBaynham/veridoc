"""Pydantic models for collection APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.document import CanonicalScoreOut, DocumentSummaryOut


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    document_count: int = Field(ge=0, description="Documents in this collection")
    created_at: datetime


class CollectionDetailOut(BaseModel):
    """Workspace header: one collection the caller can access."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str | None = Field(
        default=None,
        description="Reserved; no column in DB yet — always null until migrations add it.",
    )
    document_count: int = Field(ge=0)
    last_updated: datetime | None = Field(
        default=None,
        description="Max(documents.updated_at) in this collection.",
    )
    status_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Counts keyed by documents.status (e.g. queued, completed, failed).",
    )
    failed_document_count: int = Field(default=0, ge=0)
    in_progress_document_count: int = Field(
        default=0,
        ge=0,
        description="Documents in created or queued status (pipeline not finished).",
    )
    avg_canonical_factuality: float | None = Field(
        default=None,
        description="Mean factuality_score over canonical document_scores in this collection.",
    )
    created_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionOut]


class CollectionCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    organization_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Organization to create the collection in; omit for your primary workspace org"
        ),
    )

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v


class CollectionUpdateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v


class FacetBucketOut(BaseModel):
    key: str | None = None
    count: int = 0


class CollectionPostgresStatsOut(BaseModel):
    document_count: int = 0
    scored_documents: int = 0
    avg_factuality: float | None = None
    avg_ai_probability: float | None = None
    suspicious_count: int = 0


class CollectionAnalyticsOut(BaseModel):
    collection_id: uuid.UUID
    index_total: int = 0
    index_status: str = ""
    index_message: str | None = None
    facets: dict[str, list[FacetBucketOut]] | None = None
    postgres: CollectionPostgresStatsOut


class CollectionDocumentItemOut(DocumentSummaryOut):
    """One row in the collection document directory."""

    canonical_score: CanonicalScoreOut | None = None
    primary_source_kind: str | None = Field(
        default=None,
        description="source_kind of earliest document_sources row (upload, url, …).",
    )


class CollectionDocumentsListResponse(BaseModel):
    items: list[CollectionDocumentItemOut]
    total: int
    limit: int
    offset: int
    collection_id: uuid.UUID


class CollectionActivityItemOut(BaseModel):
    """One pipeline event scoped to a document in the collection."""

    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str | None = None
    pipeline_run_id: uuid.UUID
    event_type: str
    stage: str | None = None
    step_index: int
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class CollectionActivityResponse(BaseModel):
    items: list[CollectionActivityItemOut]
    collection_id: uuid.UUID
