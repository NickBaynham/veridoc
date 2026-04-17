"""Resolve builder callable by model_type."""

from __future__ import annotations

from collections.abc import Callable

from app.services.models.builders.base import ModelBuildContext, ModelBuilderResult
from app.services.models.builders.claims_builder import build_claims_evidence
from app.services.models.builders.software_service_builder import build_software_service
from app.services.models.builders.summary_builder import build_summary
from app.services.models.builders.test_knowledge_builder import build_test_knowledge

BuilderFn = Callable[[ModelBuildContext], ModelBuilderResult]

_BUILDERS: dict[str, BuilderFn] = {
    "summary": build_summary,
    "claims_evidence": build_claims_evidence,
    "software_service": build_software_service,
    "test_knowledge": build_test_knowledge,
}


def get_builder(model_type: str) -> BuilderFn:
    fn = _BUILDERS.get(model_type)
    if fn is None:
        raise ValueError(f"unknown model_type: {model_type}")
    return fn
