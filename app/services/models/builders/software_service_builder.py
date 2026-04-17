"""Software service model: V1 metadata-oriented scaffold."""

from __future__ import annotations

from app.services.models.builders.base import ModelBuildContext, ModelBuilderResult
from app.services.models.builders.summary_builder import build_summary


def build_software_service(ctx: ModelBuildContext) -> ModelBuilderResult:
    base = build_summary(ctx)
    base.summary["kind"] = "software_service_v1"
    base.summary["headline"] = (
        f"Software service knowledge — {base.metrics.get('document_count', 0)} artifact(s); "
        "API/service graph extraction is future work."
    )
    base.summary["services_placeholder"] = []
    base.summary["dependencies_placeholder"] = []
    return base
