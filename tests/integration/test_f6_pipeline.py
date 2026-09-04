"""
tests/integration/test_f6_pipeline.py
Integration tests: run F6 over all 12 synthetic events and compare against
the reference D6_evidence_ranking.csv.
Target: top-1 accuracy == 1.0 on the 12-event synthetic set (smoke test).
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.f6_ranking.service import rank_event
from shared.mocks.load_mock import load_mock_df as load_mock, list_events

_REF_DF = load_mock("f6")


class TestF6Pipeline:

    @pytest.fixture(scope="class")
    def all_results(self):
        events = list_events("f4")
        return {ev: rank_event(ev) for ev in events}

    def test_all_events_produce_results(self, all_results):
        """Every event must return a RankingResult without crashing."""
        for event_id, result in all_results.items():
            assert result.n_candidates >= 0
            assert result.event_id == event_id

    def test_top1_accuracy(self, all_results):
        """Rank-1 candidate must match reference for all 12 events."""
        ref = _REF_DF[_REF_DF["rank"] == 1].copy()
        correct = 0
        total = 0
        for event_id, result in all_results.items():
            if result.n_candidates == 0:
                continue
            total += 1
            top1_mmsi = result.candidates[0].candidate_mmsi
            ref_row = ref[ref["event_id"] == event_id]
            if ref_row.empty:
                continue
            ref_mmsi = str(int(ref_row["candidate_mmsi"].iloc[0]))
            if top1_mmsi == ref_mmsi:
                correct += 1
        accuracy = correct / total if total > 0 else 0.0
        assert accuracy == 1.0, (
            f"Top-1 accuracy: {correct}/{total} = {accuracy:.2%}. Expected 1.0 (12/12)."
        )

    def test_schema_compliance(self, all_results):
        """All HypothesisScore fields must satisfy schema constraints."""
        for event_id, result in all_results.items():
            for h in result.candidates:
                assert 0.0 <= h.final_score <= 1.0, f"{event_id}: score out of [0,1]"
                assert h.confidence_band in ("high", "medium", "low")
                assert h.rank >= 1
                assert h.hypothesis_id.startswith("HYP_")
                assert h.n_evidence_items >= 0
                assert 0.0 <= h.data_quality_weight <= 1.0

    def test_ranks_contiguous(self, all_results):
        """Ranks must be 1,2,3... without gaps."""
        for event_id, result in all_results.items():
            ranks = sorted(h.rank for h in result.candidates)
            assert ranks == list(range(1, len(ranks) + 1)), f"{event_id}: non-contiguous ranks {ranks}"

    def test_insufficient_events_match_reference(self, all_results):
        """Our insufficient-evidence flags must cover all reference-flagged events."""
        ref_ie = set(
            _REF_DF[_REF_DF["event_insufficient_evidence"] == True]["event_id"].unique()
        )
        our_ie = {ev for ev, r in all_results.items() if r.event_insufficient_evidence}
        for ev in ref_ie:
            assert ev in our_ie, f"{ev} not flagged insufficient by our implementation"

    def test_scores_descending(self, all_results):
        """Candidates within an event must be sorted descending by final_score."""
        for event_id, result in all_results.items():
            scores = [h.final_score for h in result.candidates]
            assert scores == sorted(scores, reverse=True), f"{event_id}: scores not descending"

    def test_five_candidates_per_event(self, all_results):
        """Each of the 12 events must have exactly 5 candidate hypotheses."""
        for event_id, result in all_results.items():
            assert result.n_candidates == 5, f"{event_id}: expected 5 candidates, got {result.n_candidates}"

    def test_explanation_labels(self, all_results):
        """Explanation string must contain all required component labels."""
        required = ["src_prob=", "spatial=", "temporal=", "drift=", "behaviour=", "contradictions=", "final="]
        for event_id, result in all_results.items():
            for h in result.candidates:
                for label in required:
                    assert label in h.explanation, f"{event_id}/{h.candidate_mmsi}: missing {label!r}"

    def test_demo_evt0002_culprit_is_top1(self, all_results):
        """EVT0002 demo: MMSI 480469227 must be rank-1 with sufficient evidence."""
        result = all_results["EVT0002"]
        top = result.candidates[0]
        assert top.candidate_mmsi == "480469227", f"Expected 480469227, got {top.candidate_mmsi}"
        assert top.is_true_source is True
        assert result.event_insufficient_evidence is False
        assert top.final_score > 0.35

    def test_demo_evt0001_insufficient(self, all_results):
        """EVT0001 demo: must be flagged insufficient (no evidence items)."""
        result = all_results["EVT0001"]
        assert result.event_insufficient_evidence is True

    def test_hypothesis_id_format(self, all_results):
        """hypothesis_id must follow HYP_<event_id>_<mmsi> pattern."""
        for event_id, result in all_results.items():
            for h in result.candidates:
                expected_prefix = f"HYP_{event_id}_"
                assert h.hypothesis_id.startswith(expected_prefix), (
                    f"Bad hypothesis_id: {h.hypothesis_id}"
                )
