"""Unit tests: Bayesian fusion log-odds math and helpers."""

from __future__ import annotations

import math

import pytest
from app.services.bayes_fusion_score import compute_fused_ai_probability


def test_fusion_no_inputs_returns_none():
    p, dbg = compute_fused_ai_probability(pi0=0.15, p_heuristic=None, p_http=None)
    assert p is None
    assert dbg.get("reason") == "no_probability_inputs"


def test_fusion_heuristic_only_matches_p_when_equal_prior():
    pi0 = 0.15
    p, dbg = compute_fused_ai_probability(pi0=pi0, p_heuristic=pi0, p_http=None)
    assert p is not None
    assert p == pytest.approx(pi0, abs=1e-3)
    assert dbg["log_odds"]["delta_heuristic"] == pytest.approx(0.0, abs=1e-5)


def test_fusion_combines_http_and_heuristic():
    p, dbg = compute_fused_ai_probability(
        pi0=0.15,
        p_heuristic=0.6,
        p_http=0.8,
        lambda_heuristic=1.0,
        lambda_http=1.0,
    )
    assert p is not None
    assert 0.001 < p < 0.999
    assert p > 0.85
    assert dbg["p_inputs"]["heuristic_ai_prob"] == 0.6
    assert dbg["p_inputs"]["http_ai_prob"] == 0.8


def test_fusion_clamps_extremes():
    p, _ = compute_fused_ai_probability(
        pi0=0.01,
        p_heuristic=0.999,
        p_http=0.999,
    )
    assert p is not None
    assert p <= 0.999


def test_lambda_http_reduces_http_influence():
    p_full, _ = compute_fused_ai_probability(
        pi0=0.15,
        p_heuristic=0.5,
        p_http=0.9,
        lambda_http=1.0,
    )
    p_damp, _ = compute_fused_ai_probability(
        pi0=0.15,
        p_heuristic=0.5,
        p_http=0.9,
        lambda_http=0.25,
    )
    assert p_full is not None and p_damp is not None
    assert p_full > p_damp


def test_http_only():
    p, dbg = compute_fused_ai_probability(pi0=0.15, p_heuristic=None, p_http=0.4)
    assert p is not None
    l0 = math.log(0.15 / 0.85)
    expected_l = l0 + (math.log(0.4 / 0.6) - l0)
    expected_p = 1 / (1 + math.exp(-expected_l))
    assert p == pytest.approx(max(0.001, min(0.999, expected_p)), rel=1e-4)
