"""Tests for F3.0 Contracts and Shared Infrastructure."""
import pytest
from pydantic import ValidationError

from shared.config.settings import get_settings
from shared.mocks.load_mock import load_mock
from shared.schemas.envelope import ApiError, ApiMeta, ApiResponse, ErrorDetail
from shared.schemas.f2_contract import CentroidCoord, GeoJSONPolygon, TemporalSpillState
from shared.schemas.f3_contract import (
    EnvironmentalStateSnapshot,
    SourceHypothesisWindow,
    SourceLocationCoord,
)
from shared.schemas.f4_contract import CandidateVessel


def test_api_response_envelope():
    """Verifies that ApiResponse envelopes payload and execution metadata."""
    meta = ApiMeta(run_id="RUN_20260904T120000Z", generated_at="2026-09-04T12:00:00Z")
    resp = ApiResponse[dict](data={"status": "ok"}, meta=meta)
    dumped = resp.model_dump()
    assert dumped["data"] == {"status": "ok"}
    assert dumped["meta"]["run_id"] == "RUN_20260904T120000Z"
    assert dumped["meta"]["generated_at"] == "2026-09-04T12:00:00Z"


def test_api_error_envelope():
    """Verifies that ApiError models error codes and messages."""
    err = ApiError(
        error=ErrorDetail(
            code="NOT_FOUND",
            message="Event not found",
            detail={"event_id": "EVT9999"},
        )
    )
    dumped = err.model_dump()
    assert dumped["error"]["code"] == "NOT_FOUND"
    assert dumped["error"]["message"] == "Event not found"
    assert dumped["error"]["detail"]["event_id"] == "EVT9999"


def test_f2_contract_valid():
    """Verifies that valid TemporalSpillState passes validation."""
    state = TemporalSpillState(
        observation_id="OBS_EVT0001_000",
        event_id="EVT0001",
        timestamp="2026-01-09T16:00:22Z",
        state_type="OBSERVED",
        polygon_geojson=GeoJSONPolygon(
            coordinates=[[[21.105, 38.363], [21.195, 38.363], [21.195, 38.337], [21.105, 38.363]]]
        ),
        area_km2=26.9,
        centroid=CentroidCoord(lat=38.363, lon=21.147),
        is_observed=True,
    )
    assert state.observation_id == "OBS_EVT0001_000"
    assert state.is_observed is True


def test_f2_contract_invalid_state_type():
    """Verifies that unapproved state types are rejected."""
    with pytest.raises(ValidationError):
        TemporalSpillState(
            observation_id="OBS_EVT0001_000",
            event_id="EVT0001",
            timestamp="2026-01-09T16:00:22Z",
            state_type="UNKNOWN_TYPE",  # Invalid
            polygon_geojson=GeoJSONPolygon(
                coordinates=[[[21.105, 38.363], [21.195, 38.363], [21.195, 38.337], [21.105, 38.363]]]
            ),
            area_km2=26.9,
            centroid=CentroidCoord(lat=38.363, lon=21.147),
            is_observed=True,
        )


def test_f3_contract_valid():
    """Verifies that valid SourceHypothesisWindow passes validation."""
    hyp = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0001_HBEST",
        event_id="EVT0001",
        source_location=SourceLocationCoord(lat=37.949, lon=21.279),
        origin_time_start="2026-01-08T14:06:30Z",
        origin_time_end="2026-01-09T02:06:30Z",
        uncertainty_radius_km=16.3,
        source_probability=1.0,
    )
    assert hyp.source_hypothesis_id == "SH_EVT0001_HBEST"
    assert hyp.uncertainty_radius_km == 16.3
    assert hyp.source_probability == 1.0


def test_f3_contract_requires_uncertainty():
    """Verifies that uncertainty_radius_km is mandatory and cannot be omitted."""
    with pytest.raises(ValidationError):
        SourceHypothesisWindow(
            source_hypothesis_id="SH_EVT0001_HBEST",
            event_id="EVT0001",
            source_location=SourceLocationCoord(lat=37.949, lon=21.279),
            origin_time_start="2026-01-08T14:06:30Z",
            origin_time_end="2026-01-09T02:06:30Z",
            # missing uncertainty_radius_km
            source_probability=1.0,
        )


def test_f3_contract_probability_range():
    """Verifies that probability must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        SourceHypothesisWindow(
            source_hypothesis_id="SH_EVT0001_HBEST",
            event_id="EVT0001",
            source_location=SourceLocationCoord(lat=37.949, lon=21.279),
            origin_time_start="2026-01-08T14:06:30Z",
            origin_time_end="2026-01-09T02:06:30Z",
            uncertainty_radius_km=16.3,
            source_probability=1.5,  # Invalid
        )


def test_settings_discovery():
    """Verifies that Settings discovers config.used.yaml without error."""
    settings = get_settings()
    assert settings.CONFIG_YAML_PATH.exists()
    cfg = settings.load_config_yaml()
    assert "hindcast" in cfg
    assert "environment" in cfg
    assert "ais" in cfg


def test_load_mock_f2():
    """Verifies that load_mock('f2', 'EVT0001') loads and validates all D2 states."""
    f2_states = load_mock("f2", "EVT0001")
    assert len(f2_states) > 0
    for s in f2_states:
        # Validate that each dictionary satisfies the TemporalSpillState contract
        model = TemporalSpillState.model_validate(s)
        assert model.event_id == "EVT0001"
        assert model.polygon_geojson.type == "Polygon"
        assert len(model.polygon_geojson.coordinates) >= 1
    # Check that observed states are present
    observed = [s for s in f2_states if s["is_observed"] is True]
    assert len(observed) > 0


def test_load_mock_f3():
    """Verifies that load_mock('f3', 'EVT0001') loads and normalizes D3 hypotheses."""
    f3_hyps = load_mock("f3", "EVT0001")
    assert len(f3_hyps) == 7  # 1 best + 6 ensemble
    hbest_found = False
    for h in f3_hyps:
        model = SourceHypothesisWindow.model_validate(h)
        assert model.event_id == "EVT0001"
        assert model.uncertainty_radius_km >= 0.0
        if model.source_hypothesis_id == "SH_EVT0001_HBEST":
            hbest_found = True
            assert model.source_probability == 1.0
            assert model.ensemble_id == -1
    assert hbest_found is True
