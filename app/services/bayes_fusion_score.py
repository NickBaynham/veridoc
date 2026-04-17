"""
Bayesian-style log-odds fusion for `document_scores` (`verifiedsignal_bayes_v1`).

See docs/scoring-bayesian-fusion.md.
"""

from __future__ import annotations

import hashlib
import logging
import math
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document, DocumentScore
from app.services.score_http_remote import HTTP_SCORER_NAME, content_fingerprint

log = logging.getLogger("verifiedsignal.bayes_fusion")

BAYES_SCORER_NAME = "verifiedsignal_bayes_v1"
BAYES_SCORER_VERSION = "1.0.0"
HEURISTIC_SCORER_NAME = "verifiedsignal_heuristic"

PROB_EPS = 1e-6
FUSED_MIN = 0.001
FUSED_MAX = 0.999


def _clamp_prob(p: float) -> float:
    return max(PROB_EPS, min(1.0 - PROB_EPS, p))


def _logit(p: float) -> float:
    p = _clamp_prob(p)
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def compute_fused_ai_probability(
    *,
    pi0: float,
    p_heuristic: float | None,
    p_http: float | None,
    lambda_heuristic: float = 1.0,
    lambda_http: float = 1.0,
) -> tuple[float | None, dict[str, Any]]:
    """
    Returns (p_fused, debug dict) or (None, reason) if no signal contributes.
    """
    if p_heuristic is None and p_http is None:
        return None, {"reason": "no_probability_inputs"}

    l0 = _logit(pi0)
    delta_h = 0.0
    delta_r = 0.0
    used_h = False
    used_r = False

    if p_heuristic is not None:
        ph = _clamp_prob(float(p_heuristic))
        delta_h = float(lambda_heuristic) * (_logit(ph) - l0)
        used_h = True
    if p_http is not None:
        pr = _clamp_prob(float(p_http))
        delta_r = float(lambda_http) * (_logit(pr) - l0)
        used_r = True

    l_fused = l0 + delta_h + delta_r
    p_raw = _sigmoid(l_fused)
    p_fused = max(FUSED_MIN, min(FUSED_MAX, p_raw))

    dbg: dict[str, Any] = {
        "kind": "bayes_fusion_v1",
        "prior": {"pi0": pi0, "source": "global_env"},
        "log_odds": {
            "prior": round(l0, 6),
            "delta_heuristic": round(delta_h, 6) if used_h else None,
            "delta_http": round(delta_r, 6) if used_r else None,
            "fused": round(l_fused, 6),
        },
        "p_inputs": {
            "heuristic_ai_prob": float(p_heuristic) if p_heuristic is not None else None,
            "http_ai_prob": float(p_http) if p_http is not None else None,
        },
        "lambdas": {
            "heuristic": float(lambda_heuristic),
            "http": float(lambda_http),
        },
        "warnings": [],
    }
    if used_h and used_r:
        dbg["warnings"].append(
            "heuristic_and_http_may_be_miscalibrated; naïve_independence_assumption"
        )
    return round(p_fused, 5), dbg


def _sha_bytes(blob: object | None) -> bytes | None:
    if blob is None:
        return None
    if isinstance(blob, memoryview):
        return blob.tobytes()
    return bytes(blob)


def _input_hash(*, heuristic_id: uuid.UUID | None, http_id: uuid.UUID | None, fp: str) -> str:
    raw = f"{heuristic_id}|{http_id}|{fp}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def _latest_heuristic_row(session: Session, document_id: uuid.UUID) -> DocumentScore | None:
    return session.scalar(
        select(DocumentScore)
        .where(
            DocumentScore.document_id == document_id,
            DocumentScore.scorer_name == HEURISTIC_SCORER_NAME,
        )
        .order_by(DocumentScore.scored_at.desc())
        .limit(1)
    )


def _latest_completed_http_row(
    session: Session, document_id: uuid.UUID, fp: str
) -> DocumentScore | None:
    rows = session.scalars(
        select(DocumentScore)
        .where(
            DocumentScore.document_id == document_id,
            DocumentScore.scorer_name == HTTP_SCORER_NAME,
        )
        .order_by(DocumentScore.scored_at.desc())
    ).all()
    for row in rows:
        pl = row.score_payload or {}
        if pl.get("job_status") != "completed":
            continue
        if pl.get("content_fingerprint") != fp:
            continue
        if row.ai_generation_probability is None:
            continue
        return row
    return None


def _fusion_row_exists(session: Session, document_id: uuid.UUID, input_hash: str) -> bool:
    rows = session.scalars(
        select(DocumentScore).where(
            DocumentScore.document_id == document_id,
            DocumentScore.scorer_name == BAYES_SCORER_NAME,
        )
    ).all()
    for row in rows:
        pl = row.score_payload or {}
        if pl.get("input_hash") == input_hash:
            return True
    return None


def _confidence_fused(h_conf: float | None, r_conf: float | None) -> float:
    vals = [v for v in (h_conf, r_conf) if v is not None]
    if not vals:
        return 0.5
    return float(min(vals))


def apply_bayes_fusion(
    session: Session,
    doc: Document,
    *,
    settings: Settings,
) -> None:
    """Insert `verifiedsignal_bayes_v1` row when enabled and inputs exist."""
    if not settings.bayes_fusion_enabled:
        return

    fp = content_fingerprint(
        body_text=doc.body_text,
        content_sha256=_sha_bytes(doc.content_sha256),
    )

    h_row = _latest_heuristic_row(session, doc.id)
    p_h = (
        float(h_row.ai_generation_probability)
        if h_row and h_row.ai_generation_probability is not None
        else None
    )

    http_row = _latest_completed_http_row(session, doc.id, fp)
    p_r = float(http_row.ai_generation_probability) if http_row else None

    http_skipped_reason: str | None = None
    if http_row is None:
        rows = session.scalars(
            select(DocumentScore)
            .where(
                DocumentScore.document_id == doc.id,
                DocumentScore.scorer_name == HTTP_SCORER_NAME,
            )
            .order_by(DocumentScore.scored_at.desc())
            .limit(1)
        ).all()
        if rows:
            pl = rows[0].score_payload or {}
            if pl.get("job_status") == "completed" and rows[0].ai_generation_probability is None:
                http_skipped_reason = "http_completed_without_ai_generation_probability"
            elif pl.get("content_fingerprint") != fp:
                http_skipped_reason = "http_completed_stale_fingerprint"
        else:
            http_skipped_reason = "no_http_row"

    lambda_h = 1.0
    lambda_r = 1.0
    if http_row is not None and http_row.confidence_score is not None:
        lambda_r = max(0.25, min(1.0, float(http_row.confidence_score)))

    p_fused, dbg = compute_fused_ai_probability(
        pi0=float(settings.bayes_fusion_prior_ai_prob),
        p_heuristic=p_h,
        p_http=p_r,
        lambda_heuristic=lambda_h,
        lambda_http=lambda_r,
    )
    if p_fused is None:
        log.info("bayes_fusion_skip document_id=%s reason=%s", doc.id, dbg.get("reason"))
        return

    ih = _input_hash(
        heuristic_id=h_row.id if h_row else None,
        http_id=http_row.id if http_row else None,
        fp=fp,
    )
    if _fusion_row_exists(session, doc.id, ih):
        log.info("bayes_fusion_idempotent_skip document_id=%s", doc.id)
        return

    dbg["content_fingerprint"] = fp
    dbg["input_hash"] = ih
    dbg["document_score_ids"] = {
        "heuristic": str(h_row.id) if h_row else None,
        "http": str(http_row.id) if http_row else None,
    }
    if http_skipped_reason and p_r is None:
        dbg["http_skipped_reason"] = http_skipped_reason

    h_conf = (
        float(h_row.confidence_score)
        if h_row and h_row.confidence_score is not None
        else None
    )
    r_conf = (
        float(http_row.confidence_score)
        if http_row and http_row.confidence_score is not None
        else None
    )
    conf_out = _confidence_fused(h_conf, r_conf)

    if settings.bayes_fusion_promote_canonical:
        session.execute(
            update(DocumentScore)
            .where(DocumentScore.document_id == doc.id)
            .values(is_canonical=False)
        )

    session.add(
        DocumentScore(
            document_id=doc.id,
            pipeline_run_id=None,
            scorer_name=BAYES_SCORER_NAME,
            scorer_version=BAYES_SCORER_VERSION,
            score_schema_version=1,
            is_canonical=settings.bayes_fusion_promote_canonical,
            factuality_score=None,
            ai_generation_probability=p_fused,
            fallacy_score=None,
            confidence_score=round(conf_out, 5),
            score_payload=dbg,
        )
    )
    log.info(
        "bayes_fusion_insert document_id=%s p_fused=%s promote=%s",
        doc.id,
        p_fused,
        settings.bayes_fusion_promote_canonical,
    )
