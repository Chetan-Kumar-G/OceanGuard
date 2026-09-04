"""Rule engine + threshold-boundary behaviour (Prompt TESTS: "behavior exactly
at the bound")."""
from __future__ import annotations

import pytest

from backend.f5_consistency.engine import ResidualSet, classify, evaluate


def test_all_within_support_is_supports(thr):
    rel, reason = classify({"spatial_residual_km": 1.0, "temporal_residual_h": 1.0}, thr)
    assert rel == "SUPPORTS"
    assert "within support bounds" in reason


def test_exactly_at_support_bound_is_supports(thr):
    # support bounds: spatial 8.0, temporal 6.0 — inclusive
    rel, _ = classify({"spatial_residual_km": 8.0, "temporal_residual_h": 6.0}, thr)
    assert rel == "SUPPORTS"


def test_just_above_support_bound_is_unknown(thr):
    rel, reason = classify({"spatial_residual_km": 8.0001, "temporal_residual_h": 1.0}, thr)
    assert rel == "UNKNOWN"
    assert "grey band" in reason


def test_exactly_at_contradict_bound_is_contradicts(thr):
    # contradict bounds: spatial 40.0, temporal 24.0 — inclusive
    rel, _ = classify({"spatial_residual_km": 40.0}, thr)
    assert rel == "CONTRADICTS"
    rel, _ = classify({"temporal_residual_h": 24.0}, thr)
    assert rel == "CONTRADICTS"


def test_just_below_contradict_bound_is_unknown(thr):
    rel, _ = classify({"spatial_residual_km": 39.999}, thr)
    assert rel == "UNKNOWN"


def test_contradict_wins_when_one_residual_hot_one_cool(thr):
    rel, reason = classify({"spatial_residual_km": 45.0, "temporal_residual_h": 1.0}, thr)
    assert rel == "CONTRADICTS"
    assert "spatial_residual_km" in reason


def test_empty_constrained_set_is_unknown(thr):
    rel, reason = classify({}, thr)
    assert rel == "UNKNOWN"
    assert "no constrained residual" in reason


def test_grey_band_between_bounds_is_unknown(thr):
    rel, _ = classify({"spatial_residual_km": 20.0}, thr)
    assert rel == "UNKNOWN"


def test_evaluate_missing_field_forces_unknown(thr):
    rs = ResidualSet()
    rs.set_constrained("spatial_residual_km", 1.0)
    rs.set_constrained("temporal_residual_h", None, missing_label="closest-approach timestamp")
    rel, reason = evaluate(rs, thr)
    assert rel == "UNKNOWN"
    assert "missing field(s)" in reason
    assert "closest-approach timestamp" in reason


def test_evaluate_missing_field_never_discards_contradicts(thr):
    """Integration rule 9: a CONTRADICTS is never softened to UNKNOWN."""
    rs = ResidualSet()
    rs.set_constrained("spatial_residual_km", 999.0)  # hot
    rs.set_constrained("temporal_residual_h", None, missing_label="closest-approach timestamp")
    rel, reason = evaluate(rs, thr)
    assert rel == "CONTRADICTS"


def test_evaluate_appends_notes(thr):
    rs = ResidualSet()
    rs.set_constrained("spatial_residual_km", 1.0)
    rs.notes.append("vessel dark over source — temporal residual not evaluable")
    rel, reason = evaluate(rs, thr)
    assert rel == "SUPPORTS"
    assert "dark over source" in reason


@pytest.mark.parametrize(
    "spatial,temporal,expected",
    [
        (0.0, 0.0, "SUPPORTS"),
        (8.0, 6.0, "SUPPORTS"),
        (8.1, 6.0, "UNKNOWN"),
        (8.0, 6.1, "UNKNOWN"),
        (40.0, 0.0, "CONTRADICTS"),
        (0.0, 24.0, "CONTRADICTS"),
        (39.9, 23.9, "UNKNOWN"),
    ],
)
def test_boundary_matrix(thr, spatial, temporal, expected):
    rel, _ = classify(
        {"spatial_residual_km": spatial, "temporal_residual_h": temporal}, thr
    )
    assert rel == expected
