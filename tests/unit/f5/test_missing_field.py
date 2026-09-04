"""Integration rule 8: a missing field needed for a residual -> UNKNOWN with a
reason stating what was missing; the pair is never silently skipped."""
from __future__ import annotations

from backend.f5_consistency.service import evaluate_event


def _loader_factory(overrides):
    """Return a loader that serves the real mocks but with per-feature row edits."""
    from shared.mocks import load_mock_rows as real

    def loader(feature, event_id=None):
        payload = real(feature, event_id)
        fn = overrides.get(feature)
        if fn:
            payload = {**payload, "rows": [fn(dict(r)) for r in payload["rows"]]}
        return payload

    return loader


def test_missing_f4_timestamp_yields_unknown_not_skip():
    def drop_ts(row):
        row["closest_approach_timestamp"] = None
        row["interpolated_closest_timestamp"] = None
        row["dark_gap_over_source"] = False
        # keep a mid-range distance so spatial alone is grey, not contradict
        row["distance_to_source_effective_km"] = 10.0
        return row

    result = evaluate_event("EVT0002", loader=_loader_factory({"f4": drop_ts}))
    f3f4 = [r for r in result.records if r.source_a_type == "F3_SOURCE_HYPOTHESIS"]
    assert f3f4, "F3<->F4 pairs must still be emitted, not skipped"
    for r in f3f4:
        assert r.relation == "UNKNOWN"
        assert "missing field(s)" in r.reason


def test_missing_distance_field_yields_unknown():
    def drop_dist(row):
        row["distance_to_source_effective_km"] = None
        # a timestamp close to EVT0003's origin_time_mid (2026-01-10T17:52:26Z) so
        # the temporal residual is benign and the ONLY problem is the missing distance
        row["closest_approach_timestamp"] = "2026-01-10T20:00:00Z"
        row["interpolated_closest_timestamp"] = None
        row["dark_gap_over_source"] = False
        return row

    result = evaluate_event("EVT0003", loader=_loader_factory({"f4": drop_dist}))
    f3f4 = [r for r in result.records if r.source_a_type == "F3_SOURCE_HYPOTHESIS"]
    assert f3f4
    assert all(r.relation == "UNKNOWN" for r in f3f4)
    assert all("distance_to_source_effective_km" in r.reason for r in f3f4)


def test_contradicts_survives_a_missing_companion_field():
    def far_but_no_ts(row):
        row["distance_to_source_effective_km"] = 200.0  # unambiguous CONTRADICTS
        row["closest_approach_timestamp"] = None
        row["interpolated_closest_timestamp"] = None
        row["dark_gap_over_source"] = False
        return row

    result = evaluate_event("EVT0004", loader=_loader_factory({"f4": far_but_no_ts}))
    f3f4 = [r for r in result.records if r.source_a_type == "F3_SOURCE_HYPOTHESIS"]
    assert f3f4
    assert all(r.relation == "CONTRADICTS" for r in f3f4)


def test_low_sensor_confidence_forces_f1f2_unknown():
    def kill_conf(row):
        row["f1_confidence"] = 0.10
        return row

    result = evaluate_event("EVT0005", loader=_loader_factory({"f2": kill_conf}))
    f1f2 = [r for r in result.records if r.kind.name == "F1_DETECTION__F2_STATE"]
    assert len(f1f2) == 1
    assert f1f2[0].relation == "UNKNOWN"
    assert "sensor confidence" in f1f2[0].reason


def test_single_observation_event_is_reported_as_skipped():
    result = evaluate_event("EVT0001")  # only 1 OBSERVED state in the reference data
    assert result.records == []
    assert result.skipped_reason is not None
    assert "OBSERVED" in result.skipped_reason
