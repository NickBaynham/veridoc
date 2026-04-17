"""Summary model: consolidated text stats from selected documents."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import Document
from app.services.models.builders.base import ModelBuildContext, ModelBuilderResult


def build_summary(ctx: ModelBuildContext) -> ModelBuilderResult:
    if not ctx.document_ids:
        return ModelBuilderResult(
            summary={
                "kind": "summary_v1",
                "headline": "Empty selection",
                "bullets": ["No documents were included in this model version."],
            },
            metrics={"document_count": 0, "total_chars": 0},
        )

    rows = list(
        ctx.session.scalars(
            select(Document).where(Document.id.in_(ctx.document_ids))
        ).all()
    )
    by_id: dict[uuid.UUID, Document] = {d.id: d for d in rows}
    ordered = [by_id[i] for i in ctx.document_ids if i in by_id]

    parts: list[str] = []
    total_chars = 0
    titles: list[str] = []
    for d in ordered:
        t = (d.title or d.original_filename or str(d.id))[:200]
        titles.append(t)
        body = d.body_text or ""
        total_chars += len(body)
        excerpt = body[:400].replace("\n", " ").strip()
        if excerpt:
            parts.append(f"- **{t}**: {excerpt}{'…' if len(body) > 400 else ''}")

    bullets = parts[:12] or ["Selected documents have no extracted body text yet."]
    headline = f"Summary over {len(ordered)} document(s), ~{total_chars} characters from sources."

    return ModelBuilderResult(
        summary={
            "kind": "summary_v1",
            "headline": headline,
            "bullets": bullets,
            "source_titles": titles,
            "future": {"entities": [], "claims": [], "risks": []},
        },
        metrics={
            "document_count": len(ordered),
            "total_chars": total_chars,
        },
    )
