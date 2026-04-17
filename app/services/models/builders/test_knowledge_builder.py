"""Test knowledge model: V1 scaffold for tests, coverage, and verification docs."""

from __future__ import annotations

from app.services.models.builders.base import ModelBuildContext, ModelBuilderResult
from app.services.models.builders.summary_builder import build_summary


def build_test_knowledge(ctx: ModelBuildContext) -> ModelBuilderResult:
    base = build_summary(ctx)
    base.summary["kind"] = "test_knowledge_v1"
    base.summary["headline"] = (
        f"Test knowledge pack — {base.metrics.get('document_count', 0)} source(s); "
        "test case linking is a future phase."
    )
    base.summary["test_artifacts_placeholder"] = []
    return base
