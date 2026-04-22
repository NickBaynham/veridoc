"""Unit tests: model write-back service validation (no Postgres)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from app.services import model_writeback_service as svc


def test_list_writebacks_rejects_bad_artifact_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock()
    mid = uuid.uuid4()
    coll = uuid.uuid4()
    m = MagicMock()
    m.collection_id = coll

    def _get_model(_s, model_id):
        return m if model_id == mid else None

    monkeypatch.setattr(svc.km_repo, "get_model", _get_model)
    monkeypatch.setattr(
        svc,
        "resolve_accessible_collection_ids",
        lambda _session, _sub, _settings: {coll},
    )

    with pytest.raises(ValueError, match="invalid artifact_kind"):
        svc.list_writebacks(
            db,
            auth_sub="sub",
            model_id=mid,
            artifact_kind="not_a_kind",
            verification_state=None,
            version_id=None,
            limit=10,
            offset=0,
        )


def test_get_writeback_none_when_model_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock()
    mid = uuid.uuid4()
    monkeypatch.setattr(svc.km_repo, "get_model", lambda _s, _mid: None)
    out = svc.get_writeback(
        db,
        auth_sub="sub",
        model_id=mid,
        writeback_id=uuid.uuid4(),
    )
    assert out is None


def test_patch_verification_rejects_bad_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock()
    mid = uuid.uuid4()
    wid = uuid.uuid4()
    coll = uuid.uuid4()
    m = MagicMock()
    m.collection_id = coll
    row = MagicMock()
    row.knowledge_model_id = mid
    row.verification_state = "accepted"

    def _get_model(_s, model_id):
        return m if model_id == mid else None

    monkeypatch.setattr(svc.km_repo, "get_model", _get_model)
    monkeypatch.setattr(
        svc,
        "resolve_accessible_collection_ids",
        lambda _session, _sub, _settings: {coll},
    )
    def _get_art(_s, model_id, artifact_id):
        return row if model_id == mid and artifact_id == wid else None

    monkeypatch.setattr(svc.wb_repo, "get_artifact_for_model", _get_art)

    from app.schemas.model_writeback import VerificationPatchIn

    body = VerificationPatchIn(verification_state="rejected")
    with pytest.raises(ValueError, match="transition not allowed"):
        svc.patch_verification(
            db,
            auth_sub="sub",
            model_id=mid,
            writeback_id=wid,
            body=body,
        )
