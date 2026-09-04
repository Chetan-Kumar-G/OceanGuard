"""Tests for F3.1 Observed-State Filtering."""
import pytest
from backend.f3_hindcast.adapter import F2StateAdapter
from shared.mocks.load_mock import load_mock
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


def test_strict_observed_filtering():
    """Verifies that INTERPOLATED and PREDICTED states are strictly filtered out."""
    states = [
        _make_dummy_state("OBS_01", "OBSERVED", True, "2026-01-08T10:00:00Z"),
        _make_dummy_state("OBS_02", "INTERPOLATED", False, "2026-01-08T12:00:00Z"),
        _make_dummy_state("OBS_03", "PREDICTED", False, "2026-01-08T14:00:00Z"),
        _make_dummy_state("OBS_04", "OBSERVED", False, "2026-01-08T16:00:00Z"),  # invalid is_observed
        _make_dummy_state("OBS_05", "OBSERVED", True, "2026-01-08T18:00:00Z"),
    ]

    filtered, meta = F2StateAdapter.prepare_seed_sequence(states)
    assert len(filtered) == 2
    assert [s.observation_id for s in filtered] == ["OBS_01", "OBS_05"]
    assert meta["observed_count"] == 2
    assert meta["interpolated_count"] == 1
    assert meta["predicted_count"] == 1
    assert meta["is_single_observation"] is False
    assert meta["data_quality_flag"] == "nominal"


def test_observed_filtering_on_mock_evt0001():
    """Verifies filtering against the real synthetic dataset for EVT0001."""
    raw_mock = load_mock("f2", "EVT0001")
    assert len(raw_mock) > 0

    observed, meta = F2StateAdapter.prepare_seed_sequence(raw_mock)
    assert len(observed) > 0
    assert meta["observed_count"] == len(observed)
    # Ensure every single retained state is truly observed
    for s in observed:
        assert s.is_observed is True
        assert s.state_type == "OBSERVED"
    # Ensure chronological order
    timestamps = [s.timestamp for s in observed]
    assert timestamps == sorted(timestamps)


def test_mixed_event_ids_rejected():
    """Verifies that a batch containing mixed event_ids raises ValueError."""
    s1 = _make_dummy_state("OBS_01", "OBSERVED", True)
    s2 = _make_dummy_state("OBS_02", "OBSERVED", True)
    s2.event_id = "EVT0002"  # Mismatch

    with pytest.raises(ValueError, match="Mixed event_ids"):
        F2StateAdapter.prepare_seed_sequence([s1, s2])
