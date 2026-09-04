"""Unit tests for F4 contracts, schemas, ID conventions, and QA isolation.

Covers:
- Test A: F3 input contract compatibility
- Test B: F4 output schema validation
- Test C: Track ID convention (TRK_<event_id>_<mmsi>)
- Test G: No QA leakage
- Test H: Event association comes from F3 window, not raw AIS
- Test I: F3 -> F4 contract round-trip using EVT0001
"""
import pytest
from pydantic import ValidationError

from shared.mocks.load_mock import load_mock
from shared.schemas.f3_contract import SourceHypothesisWindow, SourceLocationCoord
from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.agents import ProvenanceContractAgent
from backend.f4_ais.supervisor import F4AISSupervisor


def test_f3_input_contract_compatibility():
    """Test A: Verifies F4 consumes the frozen F3 SourceHypothesisWindow."""
    f3_data = {
        "source_hypothesis_id": "SH_EVT0001_HBEST",
        "event_id": "EVT0001",
        "source_location": {"lat": 36.5, "lon": 20.5},
        "origin_time_start": "2026-01-08T00:00:00Z",
        "origin_time_end": "2026-01-08T04:00:00Z",
        "uncertainty_radius_km": 15.2,
        "source_probability": 1.0,
    }
    # Validate against frozen F3 schema
    window = SourceHypothesisWindow.model_validate(f3_data)

    # F4 supervisor accepts window
    supervisor = F4AISSupervisor()
    resolved = supervisor.resolve_source_hypothesis("EVT0001", window)
    assert resolved.source_hypothesis_id == "SH_EVT0001_HBEST"
    assert resolved.event_id == "EVT0001"
    assert resolved.source_location.lat == 36.5
    assert resolved.uncertainty_radius_km == 15.2


def test_f4_output_schema_validation():
    """Test B: Verifies CandidateVessel validates with all frozen fields."""
    valid_candidate = {
        "track_id": "TRK_EVT0001_329813634",
        "event_id": "EVT0001",
        "mmsi": "329813634",
        "source_hypothesis_id": "SH_EVT0001_HBEST",
        "distance_to_source_effective_km": 42.86,
        "temporal_compatibility": 0.1107,
        "track_overlap": 0.0,
        "track_completeness": 0.2945,
        "dark_gap_over_source": False,
        "dark_gap_over_source_hours": 0.0,
        "closest_approach_is_interpolated": False,
        "speed_compatibility": 0.5,
        "course_compatibility": 0.9689,
        "ais_gap_ratio_origin_window": 1.0,
        "vessel_type": "Passenger",
    }
    model = CandidateVessel.model_validate(valid_candidate)
    assert model.track_id == "TRK_EVT0001_329813634"
    assert model.event_id == "EVT0001"
    assert model.mmsi == "329813634"
    assert model.distance_to_source_effective_km == 42.86
    assert model.speed_compatibility == 0.5
    assert model.course_compatibility == 0.9689

    # Missing required field raises ValidationError
    invalid = dict(valid_candidate)
    del invalid["temporal_compatibility"]
    with pytest.raises(ValidationError):
        CandidateVessel.model_validate(invalid)


def test_track_id_convention():
    """Test C: Verifies track ID convention is strictly TRK_<event_id>_<mmsi>."""
    agent = ProvenanceContractAgent()
    tid = agent.format_track_id("EVT0001", "123456789")
    assert tid == "TRK_EVT0001_123456789"
    assert tid.startswith("TRK_")


def test_no_qa_leakage_in_f4_payload():
    """Test G: Verifies F4 does not expose or consume QA-only fields.

    Asserts that none of the following appear in the CandidateVessel model:
    - qa_source_error_km
    - is_true_source
    - true_origin_lat
    - true_origin_lon
    """
    candidates = load_mock("f4", "EVT0001")
    assert len(candidates) > 0

    qa_forbidden = {
        "qa_source_error_km",
        "is_true_source",
        "true_origin_lat",
        "true_origin_lon",
    }

    for c in candidates:
        keys = set(c.keys())
        intersection = keys.intersection(qa_forbidden)
        assert not intersection, f"QA fields leaked into F4 candidate: {intersection}"

        # Test dumped Pydantic representation as well
        cv = CandidateVessel.model_validate(c)
        dumped_keys = set(cv.model_dump().keys())
        intersection_dumped = dumped_keys.intersection(qa_forbidden)
        assert not intersection_dumped, f"QA fields leaked in dumped model: {intersection_dumped}"


def test_event_association_from_hypothesis():
    """Test H: Verifies event_id is strictly derived from the F3 hypothesis, not raw AIS."""
    agent = ProvenanceContractAgent()
    candidate = agent.assemble_candidate(
        event_id="EVT0042",
        mmsi="987654321",
        hypothesis_id="SH_EVT0042_HBEST",
        compatibility={
            "distance_to_source_effective_km": 12.5,
            "temporal_compatibility": 0.8,
            "track_overlap": 0.5,
            "track_completeness": 0.9,
            "dark_gap_over_source": False,
            "dark_gap_over_source_hours": 0.0,
            "closest_approach_is_interpolated": False,
            "speed_compatibility": 0.7,
            "course_compatibility": 0.85,
            "ais_gap_ratio_origin_window": 0.2,
        }
    )
    assert candidate.event_id == "EVT0042"
    assert candidate.track_id == "TRK_EVT0042_987654321"


def test_f3_to_f4_round_trip_evt0001():
    """Test I: Full F3 -> F4 contract round-trip using EVT0001."""
    # 1. Load frozen F3 mock output for EVT0001
    f3_hypotheses = load_mock("f3", "EVT0001")
    hbest_raw = next(h for h in f3_hypotheses if h["source_hypothesis_id"] == "SH_EVT0001_HBEST")

    # 2. Validate F3 contract
    f3_window = SourceHypothesisWindow.model_validate(hbest_raw)
    assert f3_window.event_id == "EVT0001"
    assert f3_window.uncertainty_radius_km > 0.0

    # 3. Supply directly to F4 supervisor
    supervisor = F4AISSupervisor()
    candidates = supervisor.execute_reconstruction(
        event_id="EVT0001",
        hypothesis=f3_window,
    )

    # 4. Verify candidates were generated and match F4 contract
    assert len(candidates) > 0
    for cand in candidates:
        assert isinstance(cand, CandidateVessel)
        assert cand.event_id == "EVT0001"
        assert cand.source_hypothesis_id == "SH_EVT0001_HBEST"
        assert cand.track_id.startswith("TRK_EVT0001_")
        assert cand.distance_to_source_effective_km >= 0.0
        assert 0.0 <= cand.temporal_compatibility <= 1.0
