"""Tests for F3.1 Single-Observation Event Handling."""
import pytest
from backend.f3_hindcast.adapter import F2StateAdapter
from shared.schemas.f2_contract import CentroidCoord, GeoJSONPolygon, TemporalSpillState


def _make_dummy_state(obs_id: str, state_type: str, is_obs: bool, ts: str = "2026-01-08T10:00:00Z"):
    return TemporalSpillState(
        observation_id=obs_id,
        event_id="EVT0001",
        timestamp=ts,
        state_type=state_type,
        polygon_geojson=GeoJSONPolygon(
            coordinates=[[[21.0, 38.0], [21.1, 38.0], [21.1, 38.1], [21.0, 38.0]]]
        ),
        area_km2=5.0,
        centroid=CentroidCoord(lat=38.05, lon=21.05),
        is_observed=is_obs,
    )


def test_single_observation_graceful_handling():
    """Verifies that an event with only 1 OBSERVED state is processed gracefully."""
    states = [
        _make_dummy_state("OBS_SINGLE_01", "OBSERVED", True, "2026-01-08T10:00:00Z"),
        _make_dummy_state("OBS_INTERP_02", "INTERPOLATED", False, "2026-01-08T14:00:00Z"),
        _make_dummy_state("OBS_PRED_03", "PREDICTED", False, "2026-01-08T18:00:00Z"),
    ]

    filtered, meta = F2StateAdapter.prepare_seed_sequence(states)
    assert len(filtered) == 1
    assert filtered[0].observation_id == "OBS_SINGLE_01"
    assert meta["is_single_observation"] is True
    assert meta["data_quality_flag"] == "single_observation"
    assert meta["observed_count"] == 1
    assert meta["total_states"] == 3


def test_no_observation_event_flagged():
    """Verifies that an event with 0 OBSERVED states does not crash and is flagged."""
    states = [
        _make_dummy_state("OBS_INTERP_01", "INTERPOLATED", False),
        _make_dummy_state("OBS_PRED_02", "PREDICTED", False),
    ]

    filtered, meta = F2StateAdapter.prepare_seed_sequence(states)
    assert len(filtered) == 0
    assert meta["observed_count"] == 0
    assert meta["data_quality_flag"] == "no_observed_states"
