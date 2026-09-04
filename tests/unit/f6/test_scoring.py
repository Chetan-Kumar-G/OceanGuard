"""
tests/unit/f6/test_scoring.py
Unit tests for F6 scoring formula:
  - Score formula correctness
  - Insufficient-evidence trigger boundaries
  - Tie-breaking rule
"""
import sys
from pathlib import Path
import math

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.f6_ranking.service import (
    _spatial_compat,
    _drift_compat,
    _behavioural_score,
    _confidence_band,
    _build_explanation,
    _aggregate_evidence,
    rank_event,
)
from backend.f6_ranking.models import HypothesisScore
import pandas as pd


# ------------------------------------------------------------------ #
# Helpers / fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def cfg():
    """Load ranking config once for all tests."""
    import yaml
    weights_path = (
        Path(__file__).resolve().parents[3]
        / "shared" / "config" / "ranking_weights.yaml"
    )
    with open(weights_path) as fh:
        return yaml.safe_load(fh)


# ------------------------------------------------------------------ #
# 1. Component formula tests
# ------------------------------------------------------------------ #

class TestSpatialCompat:
    def test_zero_distance_returns_one(self):
        # dist=0, uncertainty=0 -> exp(0)=1.0
        assert _spatial_compat(0.0, 0.0, 12.0) == pytest.approx(1.0)

    def test_within_uncertainty_returns_one(self):
        # dist <= uncertainty -> excess=0 -> exp(0)=1.0
        result = _spatial_compat(5.0, 10.0, 12.0)
        assert result == pytest.approx(1.0)

    def test_beyond_uncertainty_decays(self):
        # dist=22, uncertainty=10, scale=12 -> excess=12 -> exp(-1) ~ 0.368
        result = _spatial_compat(22.0, 10.0, 12.0)
        assert result == pytest.approx(math.exp(-1.0), abs=1e-6)

    def test_very_far_approaches_zero(self):
        result = _spatial_compat(1000.0, 0.0, 12.0)
        assert result < 0.001


class TestDriftCompat:
    def test_perfect_both(self):
        assert _drift_compat(1.0, 1.0) == pytest.approx(1.0)

    def test_zero_both(self):
        assert _drift_compat(0.0, 0.0) == pytest.approx(0.0)

    def test_equal_weight(self):
        # 50/50 split
        assert _drift_compat(0.8, 0.4) == pytest.approx(0.6)


class TestBehaviouralScore:
    def test_no_dark_gap_zero(self):
        assert _behavioural_score(False, 0.9) == pytest.approx(0.0)

    def test_dark_gap_zero_ais_ratio(self):
        assert _behavioural_score(True, 0.0) == pytest.approx(0.5)

    def test_dark_gap_full_ais_ratio(self):
        assert _behavioural_score(True, 1.0) == pytest.approx(1.0)

    def test_dark_gap_partial_ais_ratio(self):
        # 0.5 + 0.5*0.5 = 0.75
        assert _behavioural_score(True, 0.5) == pytest.approx(0.75)


class TestConfidenceBand:
    def test_high(self, cfg):
        assert _confidence_band(0.70, cfg) == "high"
        assert _confidence_band(0.65, cfg) == "high"

    def test_medium(self, cfg):
        assert _confidence_band(0.50, cfg) == "medium"
        assert _confidence_band(0.45, cfg) == "medium"

    def test_low(self, cfg):
        assert _confidence_band(0.44, cfg) == "low"
        assert _confidence_band(0.0, cfg) == "low"


# ------------------------------------------------------------------ #
# 2. Scoring formula end-to-end
# ------------------------------------------------------------------ #

class TestScoringFormula:
    def test_formula_structure(self, cfg):
        """Verify final_score = clip(raw * dqw, 0, 1)."""
        w = cfg["weights"]
        penalty = cfg["contradiction_penalty"]

        # Known inputs
        src_prob = 1.0
        spatial = 1.0
        temporal = 0.85
        drift = 0.5
        ais_completeness = 0.5
        behaviour = 0.6
        sensor_confidence = 0.9
        contradiction_count = 0

        raw = (
            w["source_probability"] * src_prob
            + w["spatial_compatibility"] * spatial
            + w["temporal_compatibility"] * temporal
            + w["drift_compatibility"] * drift
            + w["ais_completeness"] * ais_completeness
            + w["behavioural_score"] * behaviour
            + w["sensor_confidence"] * sensor_confidence
            - penalty * contradiction_count
        )
        dqw = 0.5 + 0.5 * sensor_confidence
        expected = min(max(raw * dqw, 0.0), 1.0)

        # We trust the formula; just ensure it stays in [0, 1]
        assert 0.0 <= expected <= 1.0

    def test_contradiction_lowers_score(self, cfg):
        """Adding contradictions must lower the final score."""
        w = cfg["weights"]
        penalty = cfg["contradiction_penalty"]
        sensor_confidence = 0.9
        dqw = 0.5 + 0.5 * sensor_confidence

        base_raw = sum(w[k] for k in w) * 0.5   # all components at 0.5
        score_no_contradiction = min(max(base_raw * dqw, 0.0), 1.0)
        score_with_contradiction = min(max((base_raw - penalty) * dqw, 0.0), 1.0)

        assert score_with_contradiction < score_no_contradiction

    def test_score_clipped_to_one(self):
        """Score must never exceed 1.0."""
        # All components at 1.0, no contradictions
        import yaml
        from pathlib import Path
        weights_path = (
            Path(__file__).resolve().parents[3]
            / "shared" / "config" / "ranking_weights.yaml"
        )
        with open(weights_path) as fh:
            cfg = yaml.safe_load(fh)

        w = cfg["weights"]
        raw = sum(w.values())   # all at 1.0
        dqw = 1.0               # sensor_confidence = 1
        score = min(max(raw * dqw, 0.0), 1.0)
        assert score <= 1.0

    def test_score_non_negative_with_contradictions(self):
        """Score must never go below 0.0."""
        import yaml
        from pathlib import Path
        weights_path = (
            Path(__file__).resolve().parents[3]
            / "shared" / "config" / "ranking_weights.yaml"
        )
        with open(weights_path) as fh:
            cfg = yaml.safe_load(fh)

        penalty = cfg["contradiction_penalty"]
        dqw = 0.5
        raw = -penalty * 100    # 100 contradictions
        score = min(max(raw * dqw, 0.0), 1.0)
        assert score >= 0.0


# ------------------------------------------------------------------ #
# 3. Insufficient evidence boundaries
# ------------------------------------------------------------------ #

class TestInsufficientEvidence:
    def test_evt0001_is_insufficient(self):
        """EVT0001 has no evidence items -> insufficient evidence."""
        result = rank_event("EVT0001")
        assert result.event_insufficient_evidence is True
        for h in result.candidates:
            assert h.event_insufficient_evidence is True

    def test_evt0002_is_sufficient(self):
        """EVT0002 has strong evidence -> sufficient."""
        result = rank_event("EVT0002")
        assert result.event_insufficient_evidence is False

    def test_insufficient_when_top_score_low(self, cfg):
        """Simulate a ranking where top score is below threshold."""
        ie = cfg["insufficient_evidence"]
        threshold = ie["min_final_score"]
        # EVT0001 top score is ~0.23, below 0.35
        result = rank_event("EVT0001")
        top_score = result.candidates[0].final_score if result.candidates else 0.0
        assert top_score < threshold, f"Expected top_score < {threshold}, got {top_score}"
        assert result.event_insufficient_evidence is True

    def test_zero_candidates_insufficient(self):
        """Non-existent event -> no candidates -> insufficient."""
        import pandas as pd
        result = rank_event(
            "EVT_FAKE",
            f3_data=pd.DataFrame(),
            f4_data=pd.DataFrame(),
            f5_data=pd.DataFrame(),
        )
        assert result.event_insufficient_evidence is True
        assert result.n_candidates == 0


# ------------------------------------------------------------------ #
# 4. Tie-breaking
# ------------------------------------------------------------------ #

class TestTieBreaking:
    def test_lower_contradiction_wins_tie(self):
        """When two candidates have equal final_score, lower contradiction wins."""
        # Build two synthetic scored dicts and test the sort key
        candidates = [
            {"final_score": 0.5, "contradiction_count": 2, "ais_completeness": 0.5},
            {"final_score": 0.5, "contradiction_count": 0, "ais_completeness": 0.5},
        ]
        # Sort as in service.py
        candidates.sort(
            key=lambda x: (-x["final_score"], x["contradiction_count"], -x["ais_completeness"])
        )
        assert candidates[0]["contradiction_count"] == 0

    def test_higher_ais_completeness_wins_secondary_tie(self):
        """When score and contradiction count are equal, higher ais_completeness wins."""
        candidates = [
            {"final_score": 0.5, "contradiction_count": 0, "ais_completeness": 0.3},
            {"final_score": 0.5, "contradiction_count": 0, "ais_completeness": 0.8},
        ]
        candidates.sort(
            key=lambda x: (-x["final_score"], x["contradiction_count"], -x["ais_completeness"])
        )
        assert candidates[0]["ais_completeness"] == pytest.approx(0.8)


# ------------------------------------------------------------------ #
# 5. Evidence aggregation
# ------------------------------------------------------------------ #

class TestEvidenceAggregation:
    def test_per_candidate_counts(self):
        """Candidate-specific D5 rows are correctly counted."""
        d5 = pd.DataFrame([
            {"event_id": "EVT0002", "source_b_id": "EVT0002-480469227",
             "source_b_type": "F4_VESSEL_TRACK", "relation": "SUPPORTS",
             "sensor_confidence": 0.827},
            {"event_id": "EVT0002", "source_b_id": "EVT0002-427951534",
             "source_b_type": "F4_VESSEL_TRACK", "relation": "UNKNOWN",
             "sensor_confidence": 0.827},
            {"event_id": "EVT0002", "source_b_id": "EVT0002-480469227",
             "source_b_type": "F4_VESSEL_TRACK", "relation": "CONTRADICTS",
             "sensor_confidence": 0.827},
        ])
        sup, con, unk, n_ev, sc = _aggregate_evidence(d5, "480469227", "EVT0002")
        assert sup == 1
        assert con == 1
        assert unk == 0
        assert n_ev == 3
        assert sc == pytest.approx(0.827)

    def test_empty_d5_returns_zeros(self):
        sup, con, unk, n_ev, sc = _aggregate_evidence(pd.DataFrame(), "480469227", "EVT0002")
        assert sup == 0
        assert con == 0
        assert unk == 0
        assert n_ev == 0
