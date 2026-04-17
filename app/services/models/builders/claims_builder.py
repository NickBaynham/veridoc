"""Claims & evidence model: V1 placeholder with structure for future extraction."""

from __future__ import annotations

from app.services.models.builders.base import ModelBuildContext, ModelBuilderResult
from app.services.models.builders.summary_builder import build_summary


def build_claims_evidence(ctx: ModelBuildContext) -> ModelBuilderResult:
    """
    V1: reuse summary-style source aggregation; reserve slots for claims/evidence pipelines.
    """
    base = build_summary(ctx)
    base.summary["kind"] = "claims_evidence_v1"
    base.summary["headline"] = (
        f"Claims & evidence scaffold — {base.metrics.get('document_count', 0)} sources "
        "(structured extraction is a future phase)."
    )
    base.summary["claims_placeholder"] = []
    base.summary["evidence_placeholder"] = []
    return base
