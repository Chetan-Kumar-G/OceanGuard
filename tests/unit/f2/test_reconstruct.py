"""
Unit tests for F2 reconstruct.py

Covers:
1. OBSERVED states are correctly labeled with is_observed=True
2. INTERPOLATED states are NEVER labeled is_observed=True
3. PREDICTED states are NEVER labeled is_observed=True
4. insufficient_temporal_data flag set correctly
5. observation_id format (OBS_<event_id>_<seq>)
6. State ordering (ascending timestamp)
7. Single-scene event: only 1 OBSERVED, flag set, no crash
8. Empty detections: handled gracefully
9. persistence counter increments only on OBSERVED
10. centroid_displacement and area_change_pct correctly None on first state
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from backend.shared.schemas.spill_detection import SpillDetectionResult
from backend.f2_temporal.reconstruct import reconstruct_event


# ─── fixtures ─────────────────────────────────────────────────────────────────
def _make_rect_polygon(min_lon, min_lat, max_lon, max_lat):
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def _make_detection(
    event_id: str,
    seq: int,
    hours_offset: float,
    oil_present: bool = True,
    lon_offset: float = 0.0,
) -> Dict[str, Any]:
    """Create a synthetic SpillDetectionResult-compatible dict."""
    base_ts = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc) + timedelta(hours=hours_offset)
    polygon = _make_rect_polygon(20.0 + lon_offset, 38.0, 21.0 + lon_offset, 39.0) if oil_present else {"type": "Polygon", "coordinates": []}
    return SpillDetectionResult(
        scene_id=f"S1_{event_id}_{seq:02d}",
        event_id=event_id,
        acquisition_timestamp=base_ts,
        sensor="Sentinel-1",
        polarization="VV+VH",
        polygon_geojson=polygon,
        confidence=0.85 if oil_present else 0.0,
        lookalike_present=False,
        data_quality_flag="nominal",
        oil_present=oil_present,
        source_dataset="synthetic",
        area_km2=10.0 if oil_present else 0.0,
    ).model_dump()


# ─── observed labeling ────────────────────────────────────────────────────────
class TestObservedLabeling:
    def test_observed_is_observed_true(self):
        detections = [_make_detection("EVT9001", 0, 0)]
        result = reconstruct_event(detections, pred_steps=0)
        observed = [s for s in result.states if s.state_type == "OBSERVED"]
        assert all(s.is_observed is True for s in observed)

    def test_interpolated_is_observed_false(self):
        """Gap > 24h between two observations triggers INTERPOLATED states."""
        detections = [
            _make_detection("EVT9002", 0, 0.0),
            _make_detection("EVT9002", 1, 48.0, lon_offset=0.5),  # 48h gap → ~1 interp
        ]
        result = reconstruct_event(detections, interp_interval_h=24.0, pred_steps=0)
        interp_states = [s for s in result.states if s.state_type == "INTERPOLATED"]
        assert len(interp_states) >= 1, "Expected at least 1 INTERPOLATED state for 48h gap"
        assert all(s.is_observed is False for s in interp_states), \
            "INTERPOLATED states must have is_observed=False"

    def test_predicted_is_observed_false(self):
        detections = [
            _make_detection("EVT9003", 0, 0.0),
            _make_detection("EVT9003", 1, 12.0, lon_offset=0.2),
        ]
        result = reconstruct_event(detections, pred_steps=2, pred_interval_h=12.0)
        pred_states = [s for s in result.states if s.state_type == "PREDICTED"]
        assert len(pred_states) == 2
        assert all(s.is_observed is False for s in pred_states), \
            "PREDICTED states must have is_observed=False"

    def test_no_type_is_both_observed_and_nonobserved(self):
        """A state cannot be OBSERVED and is_observed=False simultaneously."""
        detections = [
            _make_detection("EVT9004", 0, 0.0),
            _make_detection("EVT9004", 1, 48.0, lon_offset=0.3),
        ]
        result = reconstruct_event(detections, pred_steps=2)
        for s in result.states:
            if s.state_type == "OBSERVED":
                assert s.is_observed is True, f"OBSERVED state {s.observation_id} has is_observed=False"
            else:
                assert s.is_observed is False, f"{s.state_type} state {s.observation_id} has is_observed=True"


# ─── insufficient_temporal_data flag ─────────────────────────────────────────
class TestInsufficientFlag:
    def test_flag_set_for_single_observation(self):
        detections = [_make_detection("EVT9005", 0, 0.0)]
        result = reconstruct_event(detections, pred_steps=0)
        assert result.insufficient_temporal_data is True

    def test_flag_not_set_for_two_observations(self):
        detections = [
            _make_detection("EVT9006", 0, 0.0),
            _make_detection("EVT9006", 1, 12.0, lon_offset=0.1),
        ]
        result = reconstruct_event(detections, pred_steps=0)
        assert result.insufficient_temporal_data is False

    def test_flag_set_for_empty_detections(self):
        result = reconstruct_event([])
        assert result.insufficient_temporal_data is True

    def test_all_no_oil_gives_insufficient_flag(self):
        detections = [
            _make_detection("EVT9007", 0, 0.0, oil_present=False),
            _make_detection("EVT9007", 1, 12.0, oil_present=False),
        ]
        result = reconstruct_event(detections, pred_steps=0)
        assert result.insufficient_temporal_data is True
        assert result.observed_count == 0


# ─── observation_id format ────────────────────────────────────────────────────
class TestObservationIdFormat:
    def test_observation_id_prefix(self):
        detections = [_make_detection("EVT9008", 0, 0.0)]
        result = reconstruct_event(detections, pred_steps=0)
        for s in result.states:
            assert s.observation_id.startswith("OBS_"), \
                f"observation_id must start with OBS_: got {s.observation_id}"

    def test_observation_id_contains_event_id(self):
        detections = [_make_detection("EVT9009", 0, 0.0)]
        result = reconstruct_event(detections, pred_steps=0)
        for s in result.states:
            assert "EVT9009" in s.observation_id

    def test_observation_id_3digit_seq(self):
        """IDs must be OBS_<event>_<3-digit-zero-padded>."""
        detections = [
            _make_detection("EVT9010", i, i * 6.0) for i in range(4)
        ]
        result = reconstruct_event(detections, pred_steps=0)
        for s in result.states:
            parts = s.observation_id.split("_")
            # OBS_EVT9010_000 → ['OBS', 'EVT9010', '000']
            seq_part = parts[-1]
            assert len(seq_part) == 3, f"Sequence part should be 3 digits: {seq_part}"
            assert seq_part.isdigit(), f"Sequence part should be all digits: {seq_part}"


# ─── timestamp ordering ───────────────────────────────────────────────────────
class TestTimestampOrder:
    def test_states_in_ascending_timestamp_order(self):
        detections = [
            _make_detection("EVT9011", 1, 12.0),   # out of order
            _make_detection("EVT9011", 0, 0.0),
            _make_detection("EVT9011", 2, 24.0),
        ]
        result = reconstruct_event(detections, pred_steps=0, interp_interval_h=100)
        timestamps = [s.timestamp for s in result.states]
        assert timestamps == sorted(timestamps), "States must be in ascending timestamp order"


# ─── persistence counter ──────────────────────────────────────────────────────
class TestPersistenceCounter:
    def test_persistence_increments_only_on_observed(self):
        detections = [
            _make_detection("EVT9012", 0, 0.0),
            _make_detection("EVT9012", 1, 48.0, lon_offset=0.2),  # 48h gap → interp
            _make_detection("EVT9012", 2, 72.0, lon_offset=0.3),
        ]
        result = reconstruct_event(detections, interp_interval_h=24.0, pred_steps=0)
        observed_states = [s for s in result.states if s.state_type == "OBSERVED"]
        persistence_values = [s.persistence for s in observed_states]
        assert persistence_values == sorted(persistence_values), "Persistence should be non-decreasing"
        # All observed states should have persistence ≥ 1
        assert all(p >= 1 for p in persistence_values)

    def test_persistence_final_value_equals_observed_count(self):
        detections = [
            _make_detection("EVT9013", 0, 0.0),
            _make_detection("EVT9013", 1, 12.0, lon_offset=0.1),
            _make_detection("EVT9013", 2, 24.0, lon_offset=0.2),
        ]
        result = reconstruct_event(detections, pred_steps=0, interp_interval_h=100)
        observed = [s for s in result.states if s.state_type == "OBSERVED"]
        assert observed[-1].persistence == len(observed)


# ─── first-state deltas are None ─────────────────────────────────────────────
class TestFirstStateDeltas:
    def test_first_state_has_none_deltas(self):
        detections = [
            _make_detection("EVT9014", 0, 0.0),
            _make_detection("EVT9014", 1, 12.0, lon_offset=0.1),
        ]
        result = reconstruct_event(detections, pred_steps=0, interp_interval_h=100)
        first = result.states[0]
        assert first.polygon_iou is None
        assert first.centroid_displacement_km is None
        assert first.area_change_pct is None

    def test_second_state_has_non_none_deltas(self):
        detections = [
            _make_detection("EVT9015", 0, 0.0),
            _make_detection("EVT9015", 1, 12.0, lon_offset=0.5),
        ]
        result = reconstruct_event(detections, pred_steps=0, interp_interval_h=100)
        second = result.states[1]
        assert second.polygon_iou is not None
        assert second.centroid_displacement_km is not None
        assert second.area_change_pct is not None


# ─── provenance / previous_observation_id ───────────────────────────────────
class TestProvenanceChaining:
    def test_first_observed_has_empty_previous_id(self):
        detections = [_make_detection("EVT9016", 0, 0.0)]
        result = reconstruct_event(detections, pred_steps=0)
        assert result.states[0].previous_observation_id == ""

    def test_observed_points_to_prior_observed_when_gap_filled(self):
        """
        When INTERPOLATED states are inserted between OBSERVED states,
        the second OBSERVED state must point to the first OBSERVED state
        (OceanGuard Blueprint #10), NOT to an INTERPOLATED state.
        """
        detections = [
            _make_detection("EVT9017", 0, 0.0),
            _make_detection("EVT9017", 1, 48.0, lon_offset=0.2),  # 48h gap -> 1 interp state
        ]
        result = reconstruct_event(detections, interp_interval_h=24.0, pred_steps=0)
        observed = [s for s in result.states if s.state_type == "OBSERVED"]
        interp = [s for s in result.states if s.state_type == "INTERPOLATED"]

        assert len(observed) == 2
        assert len(interp) >= 1

        first_obs = observed[0]
        second_obs = observed[1]

        # Second OBSERVED must link to first OBSERVED
        assert second_obs.previous_observation_id == first_obs.observation_id
        # No INTERPOLATED state ID is the parent of the second OBSERVED state
        interp_ids = {s.observation_id for s in interp}
        assert second_obs.previous_observation_id not in interp_ids

    def test_synthetic_states_do_not_become_observed_parents(self):
        """Every OBSERVED state's previous_observation_id must be either empty or another OBSERVED state."""
        detections = [
            _make_detection("EVT9018", 0, 0.0),
            _make_detection("EVT9018", 1, 72.0, lon_offset=0.2),  # large gap -> multiple interps
            _make_detection("EVT9018", 2, 144.0, lon_offset=0.4),
        ]
        result = reconstruct_event(detections, interp_interval_h=24.0, pred_steps=2)
        observed_ids = {s.observation_id for s in result.states if s.state_type == "OBSERVED"}

        for s in result.states:
            if s.state_type == "OBSERVED":
                assert s.previous_observation_id == "" or s.previous_observation_id in observed_ids
