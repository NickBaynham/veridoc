"""Allowed values for knowledge model tables (mirrors migration 006 CHECK constraints)."""

from __future__ import annotations

MODEL_TYPES: frozenset[str] = frozenset(
    {"summary", "claims_evidence", "software_service", "test_knowledge"}
)
KNOWLEDGE_MODEL_STATUS: frozenset[str] = frozenset({"active", "archived"})
VERSION_BUILD_STATUS: frozenset[str] = frozenset({"queued", "building", "completed", "failed"})
MODEL_BUILD_RUN_STATUS: frozenset[str] = frozenset({"queued", "running", "completed", "failed"})

MODEL_TYPE_LABELS: dict[str, str] = {
    "summary": "Summary Model",
    "claims_evidence": "Claims & Evidence Model",
    "software_service": "Software Service Model",
    "test_knowledge": "Test Knowledge Model",
}
