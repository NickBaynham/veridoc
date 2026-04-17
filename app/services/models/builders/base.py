"""Base types for model builders."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass
class ModelBuildContext:
    session: Session
    knowledge_model_id: uuid.UUID
    model_version_id: uuid.UUID
    model_type: str
    collection_id: uuid.UUID
    document_ids: list[uuid.UUID]
    build_profile: dict
    version_number: int


@dataclass
class ModelBuilderResult:
    """Structured output stored in knowledge_model_versions.summary_json (V1)."""

    summary: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
