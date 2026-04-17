"""API schemas for collection-scoped knowledge models (V1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.knowledge_model_constants import MODEL_TYPES


class KnowledgeModelCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    model_type: str = Field(..., max_length=64)
    selected_document_ids: list[uuid.UUID] = Field(..., min_length=1)
    build_profile: dict[str, Any] = Field(default_factory=dict)

    @field_validator("model_type")
    @classmethod
    def model_type_allowed(cls, v: str) -> str:
        if v not in MODEL_TYPES:
            raise ValueError(f"model_type must be one of: {sorted(MODEL_TYPES)}")
        return v


class KnowledgeModelVersionSummaryOut(BaseModel):
    id: uuid.UUID
    version_number: int
    build_status: str
    created_at: datetime
    completed_at: datetime | None = None
    asset_count: int = 0
    error_message: str | None = None


class KnowledgeModelListItemOut(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    name: str
    description: str | None
    model_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: KnowledgeModelVersionSummaryOut | None = None


class KnowledgeModelListResponse(BaseModel):
    items: list[KnowledgeModelListItemOut]
    collection_id: uuid.UUID


class KnowledgeModelDetailOut(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    name: str
    description: str | None
    model_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: KnowledgeModelVersionSummaryOut | None = None
    summary_json: dict[str, Any] | None = None


class KnowledgeModelVersionOut(BaseModel):
    id: uuid.UUID
    knowledge_model_id: uuid.UUID
    version_number: int
    build_status: str
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    asset_count: int = 0


class KnowledgeModelVersionListResponse(BaseModel):
    items: list[KnowledgeModelVersionOut]
    knowledge_model_id: uuid.UUID


class KnowledgeModelVersionDetailOut(BaseModel):
    id: uuid.UUID
    knowledge_model_id: uuid.UUID
    version_number: int
    build_status: str
    source_selection_snapshot_json: dict[str, Any]
    build_profile_json: dict[str, Any]
    summary_json: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    asset_count: int = 0


class KnowledgeModelAssetOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str | None = None
    original_filename: str | None = None
    inclusion_reason: str | None = None
    source_weight: float | None = None
    created_at: datetime


class KnowledgeModelAssetListResponse(BaseModel):
    items: list[KnowledgeModelAssetOut]
    model_version_id: uuid.UUID


class KnowledgeModelCreateResponse(BaseModel):
    knowledge_model: KnowledgeModelListItemOut
    version: KnowledgeModelVersionOut
    build_job_id: str | None = Field(
        default=None,
        description="ARQ job id when enqueued; null when build ran inline (e.g. test queue).",
    )
