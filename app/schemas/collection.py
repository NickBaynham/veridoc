"""Pydantic models for collection APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    document_count: int = Field(ge=0, description="Documents in this collection")
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
