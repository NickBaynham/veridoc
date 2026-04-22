"""analysis_metadata sections, document_tags, and search text helpers."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Document, DocumentTag
from app.services.exceptions import IntakeValidationError

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_TAG_LEN = 64
_MAX_TAGS_PATCH = 64


def normalize_tag_label(raw: str) -> str:
    s = raw.strip().lower()
    return s[:512] if s else ""


def _validate_tag_strings(tags: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    if len(tags) > _MAX_TAGS_PATCH:
        raise IntakeValidationError("too many tags")
    for t in tags:
        if not isinstance(t, str):
            raise IntakeValidationError("each tag must be a string")
        if _CONTROL.search(t):
            raise IntakeValidationError("tag contains invalid characters")
        s = t.strip()
        if not s:
            continue
        if len(s) > _MAX_TAG_LEN:
            raise IntakeValidationError("tag too long")
        norm = normalize_tag_label(s)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(s[:_MAX_TAG_LEN])
    return out


def _analysis_size_ok(meta: dict[str, Any], max_bytes: int) -> None:
    try:
        blob = json.dumps(meta, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as e:
        raise IntakeValidationError("analysis_metadata must be JSON-serializable") from e
    if len(blob.encode("utf-8")) > max_bytes:
        raise IntakeValidationError("analysis_metadata exceeds size limit")


def merge_analysis_metadata_section(
    session: Session,
    doc: Document,
    section: str,
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> None:
    """Replace one top-level key in ``analysis_metadata`` (worker-only)."""
    settings = settings or get_settings()
    max_b = int(settings.analysis_metadata_max_json_bytes)
    if not section or not str(section).strip():
        raise ValueError("section required")
    key = str(section).strip()
    base = dict(doc.analysis_metadata or {})
    base[key] = payload
    _analysis_size_ok(base, int(max_b))
    doc.analysis_metadata = base
    session.add(doc)


def replace_pipeline_tags(
    session: Session,
    document_id: uuid.UUID,
    tags: list[str],
    *,
    pipeline_run_id: uuid.UUID | None,
    confidence: float | None = None,
) -> None:
    session.execute(
        delete(DocumentTag).where(
            DocumentTag.document_id == document_id,
            DocumentTag.source == "pipeline",
        )
    )
    for t in _validate_tag_strings(tags):
        session.add(
            DocumentTag(
                document_id=document_id,
                tag=t,
                tag_normalized=normalize_tag_label(t),
                source="pipeline",
                pipeline_run_id=pipeline_run_id,
                confidence=confidence,
            )
        )


def list_tags_for_document(session: Session, document_id: uuid.UUID) -> list[DocumentTag]:
    stmt = (
        select(DocumentTag)
        .where(DocumentTag.document_id == document_id)
        .order_by(DocumentTag.source.asc(), DocumentTag.tag_normalized.asc())
    )
    return list(session.scalars(stmt).all())


def replace_user_tags(session: Session, document_id: uuid.UUID, tags: list[str]) -> None:
    session.execute(
        delete(DocumentTag).where(
            DocumentTag.document_id == document_id,
            DocumentTag.source == "user",
        )
    )
    for t in _validate_tag_strings(tags):
        session.add(
            DocumentTag(
                document_id=document_id,
                tag=t,
                tag_normalized=normalize_tag_label(t),
                source="user",
                pipeline_run_id=None,
                confidence=None,
            )
        )


def merge_user_metadata_shallow(doc: Document, patch: dict[str, Any]) -> None:
    if not patch:
        return
    base = dict(doc.user_metadata or {})
    for k, v in patch.items():
        if v is None:
            base.pop(str(k), None)
        else:
            base[str(k)] = v
    from app.services.user_metadata import validate_user_metadata

    doc.user_metadata = validate_user_metadata(base)


def tags_union_for_index(session: Session, document_id: uuid.UUID, user_meta: dict) -> list[str]:
    from app.services.user_metadata import extract_tags_for_index

    tags = list(dict.fromkeys(extract_tags_for_index(user_meta)))
    for row in list_tags_for_document(session, document_id):
        if row.tag and row.tag.strip():
            tags.append(row.tag.strip()[:_MAX_TAG_LEN])
    return list(dict.fromkeys(tags))[:128]


def flatten_analysis_for_search_text(meta: dict[str, Any], *, max_chars: int = 4000) -> str:
    """Primitive string/number values from extract/enrich sections for OpenSearch."""
    parts: list[str] = []
    for section in ("extract", "enrich", "tagging"):
        block = meta.get(section)
        if not isinstance(block, dict):
            continue
        for k, v in sorted(block.items(), key=lambda kv: kv[0]):
            if k == "schema_version":
                continue
            if isinstance(v, str):
                s = v.strip()
                if s:
                    parts.append(s)
            elif isinstance(v, (int, float, bool)):
                parts.append(str(v))
            elif isinstance(v, list) and k in ("topics", "suggested"):
                for x in v:
                    if isinstance(x, str) and x.strip():
                        parts.append(x.strip())
    text = " ".join(parts)
    return text[:max_chars]
