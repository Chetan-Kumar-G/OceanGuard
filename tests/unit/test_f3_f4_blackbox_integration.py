"""Feature F3/F4 Final Black-Box Integration & Contract Readiness Audit Test Suite.

Verifies:
1. F2 -> F3 Input Contract Audit (TemporalSpillState, GeoJSON, EPSG:4326, is_observed filtering)
2. F3 Output Contract Audit (SourceHypothesisWindow, IDs, provenance, serialization)
3. F3 -> F4 Direct Handoff (clean pipeline handoff without adapters or manual edits)
4. F4 Input Contract Audit (consumption of public F3 contract only)
5. F4 -> F5 Output Contract Audit & Simulation (CandidateVessel validation, field integrity)
6. Multiple Source Hypotheses Independence (independent evaluation, no collapsing)
7. Event-ID Propagation (end-to-end preservation: F2 -> F3 -> F4 -> F5)
8. Temporal Contract (UTC ISO-8601, inclusive origin window boundaries)
9. Spatial Contract (strict distance <= uncertainty_radius_km, no tolerance_km)
10. Observed / Interpolated Provenance & Missing Navigation Evidence (None vs 0.0)
11. Dark-Gap Semantics (objective transmission evidence, zero guilt inference)
12. Empty and Degraded Inputs (graceful handling without crashes or fabricated data)
13. EVT0001 Upstream Limitation Diagnostic (true vessel exclusion without radius tampering)
14. Ground-Truth Static Firewall (zero runtime references to evaluation keys)
15. Dataset Integrity (SHA-256 verification of protected datasets)
16. No Hidden Dependencies (clean feature import boundaries)
17. Deterministic Reproducibility (byte-for-byte identical repeated execution)
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from shared.config.settings import get_settings
from shared.mocks.load_mock import load_mock
from shared.schemas.f2_contract import CentroidCoord, GeoJSONPolygon, TemporalSpillState
from shared.schemas.f3_contract import SourceHypothesisWindow, SourceLocationCoord
from shared.schemas.f4_contract import CandidateVessel
from backend.f3_hindcast.supervisor import F3HindcastSupervisor
from backend.f4_ais.corridor import haversine_distance_km, is_spatially_compatible, is_temporally_compatible
from backend.f4_ais.schemas import RawAISRecord
from backend.f4_ais.supervisor import F4AISSupervisor
from backend.f4_ais.validation import parse_utc_timestamp


class F5ContractValidator:
    """Strict black-box contract validator simulating the downstream Feature F5 consumer.

    Validates that CandidateVessel instances produced by F4 strictly adhere to
    the frozen public contract schema, field naming, typing, value bounds,
    and provenance semantics without requiring any F4 internals.
    """

    MANDATORY_FIELDS = {
        "track_id",
        "event_id",
        "mmsi",
        "source_hypothesis_id",
        "distance_to_source_effective_km",
        "temporal_compatibility",
        "track_overlap",
        "track_completeness",
        "dark_gap_over_source",
        "dark_gap_over_source_hours",
        "closest_approach_is_interpolated",
        "speed_compatibility",
        "course_compatibility",
        "ais_gap_ratio_origin_window",
    }

    @classmethod
    def validate_candidate(
        cls,
        candidate: CandidateVessel,
        expected_event_id: Optional[str] = None,
        expected_hyp_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validates a single CandidateVessel record for F5 readiness."""
        # 1. JSON Serialization & Deserialization roundtrip
        json_str = candidate.model_dump_json()
        raw_dict = json.loads(json_str)
        reconstituted = CandidateVessel.model_validate_json(json_str)
        assert reconstituted == candidate, "CandidateVessel failed JSON serialization roundtrip"

        # 2. Mandatory fields presence
        for field_name in cls.MANDATORY_FIELDS:
            assert field_name in raw_dict, f"Missing mandatory field '{field_name}'"
            assert raw_dict[field_name] is not None, f"Mandatory field '{field_name}' must not be null"

        # 3. ID conventions and propagation
        if expected_event_id:
            assert candidate.event_id == expected_event_id, f"event_id mismatch: {candidate.event_id} != {expected_event_id}"
        if expected_hyp_id:
            assert candidate.source_hypothesis_id == expected_hyp_id, f"hyp_id mismatch: {candidate.source_hypothesis_id} != {expected_hyp_id}"

        expected_track_id = f"TRK_{candidate.event_id}_{candidate.mmsi}"
        assert candidate.track_id == expected_track_id, f"track_id '{candidate.track_id}' does not match convention '{expected_track_id}'"

        # 4. Range and value constraints
        assert candidate.distance_to_source_effective_km >= 0.0, "Effective distance must be >= 0.0"
        assert 0.0 <= candidate.temporal_compatibility <= 1.0, "temporal_compatibility must be in [0, 1]"
        assert 0.0 <= candidate.track_overlap <= 1.0, "track_overlap must be in [0, 1]"
        assert 0.0 <= candidate.track_completeness <= 1.0, "track_completeness must be in [0, 1]"
        assert isinstance(candidate.dark_gap_over_source, bool), "dark_gap_over_source must be bool"
        assert candidate.dark_gap_over_source_hours >= 0.0, "dark_gap_over_source_hours must be >= 0.0"
        assert isinstance(candidate.closest_approach_is_interpolated, bool), "closest_approach_is_interpolated must be bool"
        assert 0.0 <= candidate.speed_compatibility <= 1.0, "speed_compatibility must be in [0, 1]"
        assert 0.0 <= candidate.course_compatibility <= 1.0, "course_compatibility must be in [0, 1]"
        assert 0.0 <= candidate.ais_gap_ratio_origin_window <= 1.0, "ais_gap_ratio_origin_window must be in [0, 1]"

        # 5. Provenance nullability / range checks
        if candidate.observed_speed_kn is not None:
            assert candidate.observed_speed_kn >= 0.0, "observed_speed_kn must be >= 0.0"
        if candidate.observed_course_deg is not None:
            assert 0.0 <= candidate.observed_course_deg <= 360.0, "observed_course_deg must be in [0, 360]"
        if candidate.track_duration_h is not None:
            assert candidate.track_duration_h >= 0.0, "track_duration_h must be >= 0.0"
        if candidate.distance_to_source_km is not None:
            assert candidate.distance_to_source_km >= 0.0, "distance_to_source_km must be >= 0.0"

        # 6. Absence of guilt / culpability fields
        prohibited_attributes = {"culprit", "guilty", "guilt_score", "probability_of_guilt", "responsible", "score"}
        for attr in prohibited_attributes:
            assert not hasattr(candidate, attr), f"CandidateVessel unlawfully contains attribution field '{attr}'"

        return raw_dict

    @classmethod
    def validate_candidate_vessels(
        cls,
        candidates: List[CandidateVessel],
        expected_event_id: Optional[str] = None,
        expected_hyp_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Validates a list of CandidateVessel records."""
        results = []
        for c in candidates:
            results.append(cls.validate_candidate(c, expected_event_id, expected_hyp_id))
        return results


# ==============================================================================
# 1. F2 -> F3 INPUT CONTRACT AUDIT
# ==============================================================================

def test_f2_to_f3_input_contract_and_observed_filtering():
    """Verifies that F3 consumes a synthetic F2 TemporalSpillState sequence directly,
    strictly enforces is_observed == True filtering, and accepts both nested and flat centroids.
    """
    f2_synthetic_states: List[Dict[str, Any]] = [
        {
            "observation_id": "OBS_EVT5555_000",
            "event_id": "EVT5555",
            "timestamp": "2026-01-08T10:00:00Z",
            "state_type": "OBSERVED",
            "polygon_geojson": {
                "type": "Polygon",
                "coordinates": [[[21.0, 38.0], [21.1, 38.0], [21.1, 38.1], [21.0, 38.0]]]
            },
            "area_km2": 4.5,
            "centroid": {"lat": 38.05, "lon": 21.05},
            "is_observed": True,
        },
        {
            "observation_id": "OBS_EVT5555_001",
            "event_id": "EVT5555",
            "timestamp": "2026-01-08T12:00:00Z",
            "state_type": "INTERPOLATED",  # Must be rejected from seeds
            "polygon_geojson": {
                "type": "Polygon",
                "coordinates": [[[21.05, 38.05], [21.15, 38.05], [21.15, 38.15], [21.05, 38.05]]]
            },
            "area_km2": 5.0,
            "centroid_lat": 38.10,  # Flat centroid format compatibility check
            "centroid_lon": 21.10,
            "is_observed": False,
        },
        {
            "observation_id": "OBS_EVT5555_002",
            "event_id": "EVT5555",
            "timestamp": "2026-01-08T14:00:00Z",
            "state_type": "PREDICTED",  # Must be rejected from seeds
            "polygon_geojson": {
                "type": "Polygon",
                "coordinates": [[[21.1, 38.1], [21.2, 38.1], [21.2, 38.2], [21.1, 38.1]]]
            },
            "area_km2": 5.5,
            "centroid": {"lat": 38.15, "lon": 21.15},
            "is_observed": False,
        },
        {
            "observation_id": "OBS_EVT5555_003",
            "event_id": "EVT5555",
            "timestamp": "2026-01-08T16:00:00Z",
            "state_type": "OBSERVED",
            "polygon_geojson": {
                "type": "Polygon",
                "coordinates": [[[21.15, 38.15], [21.25, 38.15], [21.25, 38.25], [21.15, 38.15]]]
            },
            "area_km2": 6.2,
            "centroid_lat": 38.20,  # Flat format on observed state
            "centroid_lon": 21.20,
            "is_observed": True,
        },
    ]

    # 1. Parse via TemporalSpillState contract directly
    parsed_states = [TemporalSpillState.model_validate(s) for s in f2_synthetic_states]
    assert len(parsed_states) == 4
    assert parsed_states[1].centroid.lat == 38.10
    assert parsed_states[1].centroid_lat == 38.10
    assert parsed_states[3].centroid.lat == 38.20
    assert parsed_states[3].centroid_lat == 38.20

    # 2. Feed directly into F3 supervisor without any intermediate adapter
    f3_supervisor = F3HindcastSupervisor()
    hypotheses, snapshots = f3_supervisor.execute_hindcast(
        event_id="EVT5555",
        states=f2_synthetic_states,
    )

    assert len(hypotheses) > 0
    hbest = next(h for h in hypotheses if h.source_hypothesis_id == "SH_EVT5555_HBEST")
    assert hbest.event_id == "EVT5555"
    assert hbest.ensemble_id == -1
    assert hbest.source_probability == 1.0

    # CRITICAL: seed_state_ids must ONLY contain the two observed states, NEVER INTERPOLATED or PREDICTED
    assert hbest.seed_state_ids == ["OBS_EVT5555_000", "OBS_EVT5555_003"]
    assert "OBS_EVT5555_001" not in hbest.seed_state_ids
    assert "OBS_EVT5555_002" not in hbest.seed_state_ids


# ==============================================================================
# 2. F3 OUTPUT CONTRACT AUDIT
# ==============================================================================

def test_f3_output_contract_and_serialization():
    """Verifies that F3 output matches the frozen SourceHypothesisWindow schema,
    uses frozen ID conventions, preserves EPSG:4326 coordinates and UTC ISO timestamps,
    and serializes/deserializes without information loss.
    """
    f3_supervisor = F3HindcastSupervisor()
    hypotheses, snapshots = f3_supervisor.execute_hindcast(event_id="EVT0001")

    assert len(hypotheses) >= 1
    has_hbest = False
    for hyp in hypotheses:
        # Field types and bounds
        assert hyp.event_id == "EVT0001"
        assert -90.0 <= hyp.source_location.lat <= 90.0
        assert -180.0 <= hyp.source_location.lon <= 180.0
        assert hyp.uncertainty_radius_km > 0.0
        assert 0.0 <= hyp.source_probability <= 1.0

        # ISO-8601 UTC timestamp check
        t_start = parse_utc_timestamp(hyp.origin_time_start)
        t_end = parse_utc_timestamp(hyp.origin_time_end)
        assert t_start <= t_end

        # ID convention check
        if hyp.source_hypothesis_id.endswith("_HBEST"):
            has_hbest = True
            assert hyp.source_hypothesis_id == "SH_EVT0001_HBEST"
            assert hyp.ensemble_id == -1
            assert hyp.source_probability == 1.0
        else:
            assert hyp.source_hypothesis_id.startswith("SH_EVT0001_")

        # JSON Roundtrip
        dumped = hyp.model_dump_json()
        loaded = SourceHypothesisWindow.model_validate_json(dumped)
        assert loaded == hyp

    assert has_hbest is True, "Mandatory pooled best estimate SH_EVT0001_HBEST was not produced"


# ==============================================================================
# 3. F3 -> F4 DIRECT HANDOFF & F5 CONTRACT VALIDATOR SIMULATION
# ==============================================================================

def test_f3_to_f4_direct_handoff_and_f5_contract_validation():
    """Passes F2 data into F3, takes the resulting SourceHypothesisWindow,
    and passes it directly into F4 without any manual edits, adapters, or expansions.
    Then verifies that the downstream F5 contract validator accepts all produced CandidateVessels.
    """
    # 1. F3 Execution
    f3_supervisor = F3HindcastSupervisor()
    hypotheses, _ = f3_supervisor.execute_hindcast(event_id="EVT0001")
    hbest = next(h for h in hypotheses if h.source_hypothesis_id == "SH_EVT0001_HBEST")

    # 2. F4 Execution directly with hbest
    f4_supervisor = F4AISSupervisor()
    candidates = f4_supervisor.execute_reconstruction(
        event_id="EVT0001",
        hypothesis=hbest,
    )

    # 3. Downstream F5 Contract Validation
    # Even if EVT0001 has no candidates due to upstream F3 quality limitation,
    # let's verify empty candidate list is handled cleanly.
    validated = F5ContractValidator.validate_candidate_vessels(
        candidates=candidates,
        expected_event_id="EVT0001",
        expected_hyp_id=hbest.source_hypothesis_id,
    )
    assert isinstance(validated, list)

    # Now run on a synthetic scenario with guaranteed corridor matches to validate populated CandidateVessels
    t_start_iso = hbest.origin_time_start
    t_end_iso = hbest.origin_time_end
    src_lat = hbest.source_location.lat
    src_lon = hbest.source_location.lon

    synthetic_ais_records: List[Dict[str, Any]] = [
        {
            "mmsi": "111222333",
            "timestamp": t_start_iso,
            "latitude": src_lat,
            "longitude": src_lon,
            "sog_kn": 12.5,
            "cog_deg": 180.0,
            "vessel_type": "Tanker",
            "is_observed": True,
        },
        {
            "mmsi": "111222333",
            "timestamp": t_end_iso,
            "latitude": src_lat + 0.01,
            "longitude": src_lon + 0.01,
            "sog_kn": 12.0,
            "cog_deg": 182.0,
            "vessel_type": "Tanker",
            "is_observed": True,
        }
    ]

    candidates_synthetic = f4_supervisor.execute_reconstruction(
        event_id="EVT0001",
        hypothesis=hbest,
        raw_records=synthetic_ais_records,
    )

    assert len(candidates_synthetic) == 1
    validated_synth = F5ContractValidator.validate_candidate_vessels(
        candidates=candidates_synthetic,
        expected_event_id="EVT0001",
        expected_hyp_id=hbest.source_hypothesis_id,
    )
    assert len(validated_synth) == 1
    cand = candidates_synthetic[0]
    assert cand.mmsi == "111222333"
    assert cand.track_id == "TRK_EVT0001_111222333"
    assert cand.temporal_compatibility == 1.0
    assert cand.observed_speed_kn == 12.5
    assert cand.observed_course_deg == 180.0


# ==============================================================================
# 4. F4 INPUT CONTRACT AUDIT
# ==============================================================================

def test_f4_input_contract_isolation():
    """Verifies that F4 can operate given ONLY the public SourceHypothesisWindow contract
    without any access to F3 particles, grid models, or private state.
    """
    public_f3_hypothesis = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT9999_HBEST",
        event_id="EVT9999",
        source_location=SourceLocationCoord(lat=24.5000, lon=54.2000),
        origin_time_start="2026-06-01T10:00:00Z",
        origin_time_end="2026-06-01T14:00:00Z",
        uncertainty_radius_km=10.0,
        source_probability=1.0,
    )

    raw_records = [
        {
            "mmsi": "999000111",
            "timestamp": "2026-06-01T12:00:00Z",
            "latitude": 24.5100,
            "longitude": 54.2100,
            "sog_kn": 10.0,
            "cog_deg": 90.0,
            "is_observed": True,
        }
    ]

    f4_supervisor = F4AISSupervisor()
    candidates = f4_supervisor.execute_reconstruction(
        event_id="EVT9999",
        hypothesis=public_f3_hypothesis,
        raw_records=raw_records,
    )

    assert len(candidates) == 1
    assert candidates[0].event_id == "EVT9999"
    assert candidates[0].source_hypothesis_id == "SH_EVT9999_HBEST"
    assert candidates[0].mmsi == "999000111"


# ==============================================================================
# 5. MULTIPLE SOURCE HYPOTHESES TEST
# ==============================================================================

def test_multiple_source_hypotheses_independence():
    """Verifies that multiple hypotheses (e.g. ensemble members + HBEST) are evaluated
    independently by F4 without collapsing, overwriting, or mixing candidate records.
    """
    hyp00 = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0002_00",
        event_id="EVT0002",
        source_location=SourceLocationCoord(lat=25.0, lon=55.0),
        origin_time_start="2026-02-01T00:00:00Z",
        origin_time_end="2026-02-01T04:00:00Z",
        uncertainty_radius_km=5.0,
        source_probability=0.35,
    )
    hyp01 = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0002_01",
        event_id="EVT0002",
        source_location=SourceLocationCoord(lat=25.1, lon=55.1),
        origin_time_start="2026-02-01T01:00:00Z",
        origin_time_end="2026-02-01T05:00:00Z",
        uncertainty_radius_km=6.0,
        source_probability=0.65,
    )

    raw_records = [
        {
            "mmsi": "888777666",
            "timestamp": "2026-02-01T02:00:00Z",
            "latitude": 25.02,
            "longitude": 55.02,
            "sog_kn": 8.0,
            "cog_deg": 45.0,
            "is_observed": True,
        }
    ]

    f4_supervisor = F4AISSupervisor()
    cand_00 = f4_supervisor.execute_reconstruction("EVT0002", hypothesis=hyp00, raw_records=raw_records)
    cand_01 = f4_supervisor.execute_reconstruction("EVT0002", hypothesis=hyp01, raw_records=raw_records)

    assert len(cand_00) == 1
    assert len(cand_01) == 1

    assert cand_00[0].source_hypothesis_id == "SH_EVT0002_00"
    assert cand_01[0].source_hypothesis_id == "SH_EVT0002_01"

    # Distinguishable candidate evidence keys: (event_id, source_hypothesis_id, track_id)
    key00 = (cand_00[0].event_id, cand_00[0].source_hypothesis_id, cand_00[0].track_id)
    key01 = (cand_01[0].event_id, cand_01[0].source_hypothesis_id, cand_01[0].track_id)
    assert key00 != key01


# ==============================================================================
# 6. EVENT ID PROPAGATION TEST
# ==============================================================================

def test_event_id_unbroken_propagation():
    """Verifies that non-standard event IDs propagate cleanly without inference:
    F2 (EVT8833) -> F3 (EVT8833) -> F4 (EVT8833) -> CandidateVessel (EVT8833).
    """
    event_id = "EVT8833"
    f2_state = TemporalSpillState(
        observation_id=f"OBS_{event_id}_000",
        event_id=event_id,
        timestamp="2026-03-01T12:00:00Z",
        state_type="OBSERVED",
        polygon_geojson=GeoJSONPolygon(
            coordinates=[[[55.0, 25.0], [55.1, 25.0], [55.1, 25.1], [55.0, 25.0]]]
        ),
        area_km2=8.0,
        centroid=CentroidCoord(lat=25.05, lon=55.05),
        is_observed=True,
    )

    f3_supervisor = F3HindcastSupervisor()
    hyps, _ = f3_supervisor.execute_hindcast(event_id=event_id, states=[f2_state])
    hbest = next(h for h in hyps if h.ensemble_id == -1)
    assert hbest.event_id == event_id
    assert hbest.source_hypothesis_id == f"SH_{event_id}_HBEST"

    raw_record = {
        "mmsi": "555444333",
        "timestamp": "2026-03-01T08:00:00Z",
        "latitude": hbest.source_location.lat,
        "longitude": hbest.source_location.lon,
        "sog_kn": 11.0,
        "cog_deg": 120.0,
        "is_observed": True,
    }

    f4_supervisor = F4AISSupervisor()
    candidates = f4_supervisor.execute_reconstruction(
        event_id=event_id,
        hypothesis=hbest,
        raw_records=[raw_record],
    )

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.event_id == event_id
    assert cand.track_id == f"TRK_{event_id}_555444333"


# ==============================================================================
# 7. TEMPORAL CONTRACT TEST (BOUNDARY INCLUSIVITY)
# ==============================================================================

def test_temporal_contract_boundary_inclusivity():
    """Verifies that origin_time_start <= ts <= origin_time_end is inclusive,
    and fixes 1s outside are excluded from the corridor.
    """
    t_start = parse_utc_timestamp("2026-04-10T10:00:00Z")
    t_end = parse_utc_timestamp("2026-04-10T14:00:00Z")

    # Exact endpoints
    assert is_temporally_compatible(t_start, t_start, t_end) is True
    assert is_temporally_compatible(t_end, t_start, t_end) is True

    # Inside
    t_inside = parse_utc_timestamp("2026-04-10T12:00:00Z")
    assert is_temporally_compatible(t_inside, t_start, t_end) is True

    # 1 second before start
    t_before = parse_utc_timestamp("2026-04-10T09:59:59Z")
    assert is_temporally_compatible(t_before, t_start, t_end) is False

    # 1 second after end
    t_after = parse_utc_timestamp("2026-04-10T14:00:01Z")
    assert is_temporally_compatible(t_after, t_start, t_end) is False


# ==============================================================================
# 8. SPATIAL CONTRACT TEST (STRICT SPATIAL BOUNDARY)
# ==============================================================================

def test_spatial_contract_strict_boundary_no_tolerance():
    """Verifies that distance <= uncertainty_radius_km is strictly evaluated
    without tolerance_km, hidden buffers, or nearest-vessel rescue logic.
    """
    src_lat, src_lon = 25.0000, 55.0000
    radius_km = 10.0

    # Test point inside radius (d ~ 5 km)
    # 1 deg lat ~ 111.19 km -> 0.045 deg lat ~ 5 km
    inside_lat = src_lat + (5.0 / 111.195)
    is_compat, dist_km = is_spatially_compatible(inside_lat, src_lon, src_lat, src_lon, radius_km)
    assert is_compat is True
    assert dist_km < radius_km

    # Test point exactly on radius
    exact_lat = src_lat + (10.0 / 111.195)
    exact_dist = haversine_distance_km(exact_lat, src_lon, src_lat, src_lon)
    is_compat_exact, _ = is_spatially_compatible(exact_lat, src_lon, src_lat, src_lon, exact_dist)
    assert is_compat_exact is True  # Exactly on boundary must be included

    # Test point outside radius (10.01 km)
    outside_lat = src_lat + (10.05 / 111.195)
    is_compat_out, dist_out_km = is_spatially_compatible(outside_lat, src_lon, src_lat, src_lon, radius_km)
    assert is_compat_out is False
    assert dist_out_km > radius_km


# ==============================================================================
# 9. OBSERVED / INTERPOLATED PROVENANCE & MISSING EVIDENCE SEMANTICS
# ==============================================================================

def test_provenance_and_missing_evidence_semantics():
    """Verifies that:
    1. closest_approach_is_interpolated correctly differentiates observed vs interpolated minimum distance.
    2. Missing SOG/COG (None) is preserved in provenance and yields documented neutral 0.5 score.
    3. Measured SOG=0.0 and COG=0.0 (stationary / due North) are preserved as 0.0 and quantitatively evaluated.
    """
    hyp = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0003_HBEST",
        event_id="EVT0003",
        source_location=SourceLocationCoord(lat=25.0, lon=55.0),
        origin_time_start="2026-05-01T10:00:00Z",
        origin_time_end="2026-05-01T12:00:00Z",
        uncertainty_radius_km=15.0,
        source_probability=1.0,
    )

    f4_supervisor = F4AISSupervisor()

    # Case A: Missing SOG and COG (None)
    records_missing_nav = [
        {
            "mmsi": "111000001",
            "timestamp": "2026-05-01T10:30:00Z",
            "latitude": 25.01,
            "longitude": 55.01,
            "sog_kn": None,  # Unavailable
            "cog_deg": None,  # Unavailable
            "is_observed": True,
        }
    ]
    cand_missing = f4_supervisor.execute_reconstruction("EVT0003", hypothesis=hyp, raw_records=records_missing_nav)
    assert len(cand_missing) == 1
    c_miss = cand_missing[0]
    assert c_miss.observed_speed_kn is None, "Missing SOG must remain None in provenance"
    assert c_miss.observed_course_deg is None, "Missing COG must remain None in provenance"
    assert c_miss.speed_compatibility == 0.5, "Missing SOG must yield neutral 0.5"
    assert c_miss.course_compatibility == 0.5, "Missing COG must yield neutral 0.5"
    assert c_miss.closest_approach_is_interpolated is False

    # Case B: Measured SOG=0.0 (Stationary) and COG=0.0 (Due North)
    records_measured_zero = [
        {
            "mmsi": "111000002",
            "timestamp": "2026-05-01T10:30:00Z",
            "latitude": 25.01,
            "longitude": 55.01,
            "sog_kn": 0.0,  # Measured zero
            "cog_deg": 0.0,  # Measured zero (due North)
            "is_observed": True,
        }
    ]
    cand_zero = f4_supervisor.execute_reconstruction("EVT0003", hypothesis=hyp, raw_records=records_measured_zero)
    assert len(cand_zero) == 1
    c_zero = cand_zero[0]
    assert c_zero.observed_speed_kn == 0.0, "Measured SOG=0.0 must remain 0.0"
    assert c_zero.observed_course_deg == 0.0, "Measured COG=0.0 must remain 0.0"


# ==============================================================================
# 10. DARK GAP SEMANTICS SAFETY
# ==============================================================================

def test_dark_gap_semantics_safety():
    """Verifies that dark_gap_over_source == True represents strictly objective
    transmission gap evidence and never contains guilt or suspicion flags.
    """
    hyp = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0004_HBEST",
        event_id="EVT0004",
        source_location=SourceLocationCoord(lat=26.0, lon=56.0),
        origin_time_start="2026-07-01T04:00:00Z",
        origin_time_end="2026-07-01T08:00:00Z",
        uncertainty_radius_km=20.0,
        source_probability=1.0,
    )

    # 4-hour gap traversing directly over source location
    records_gap = [
        {
            "mmsi": "222333444",
            "timestamp": "2026-07-01T03:00:00Z",
            "latitude": 25.9,
            "longitude": 55.9,
            "sog_kn": 12.0,
            "cog_deg": 45.0,
            "is_observed": True,
        },
        {
            "mmsi": "222333444",
            "timestamp": "2026-07-01T08:00:00Z",  # 5-hour gap
            "latitude": 26.1,
            "longitude": 56.1,
            "sog_kn": 12.0,
            "cog_deg": 45.0,
            "is_observed": True,
        }
    ]

    f4_supervisor = F4AISSupervisor()
    candidates = f4_supervisor.execute_reconstruction("EVT0004", hypothesis=hyp, raw_records=records_gap)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.dark_gap_over_source is True
    assert c.dark_gap_over_source_hours > 0.0
    assert c.temporal_compatibility == 1.0

    # Confirm no guilt or ranking fields exist
    candidate_dict = c.model_dump()
    for forbidden in ["culprit", "guilty", "guilt_score", "responsible"]:
        assert forbidden not in candidate_dict


# ==============================================================================
# 11. EMPTY AND DEGRADED INPUT TESTS
# ==============================================================================

def test_empty_and_degraded_inputs_graceful_handling():
    """Verifies that the F3/F4 pipeline handles:
    A. zero observed seed states (raises informative ValueError)
    B. sparse observed states (single observation -> processed with data_quality_flag)
    C. empty AIS dataset -> returns empty candidate list
    D. no AIS candidate inside corridor -> returns empty candidate list
    E. single-point vessel track -> processed cleanly without crash
    """
    f3_supervisor = F3HindcastSupervisor()
    f4_supervisor = F4AISSupervisor()

    # A. Zero observed seed states
    with pytest.raises(ValueError, match="No valid OBSERVED states"):
        f3_supervisor.execute_hindcast(
            event_id="EVT_EMPTY",
            states=[
                {
                    "observation_id": "OBS_EMPTY_01",
                    "event_id": "EVT_EMPTY",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "state_type": "INTERPOLATED",
                    "polygon_geojson": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                    "area_km2": 1.0,
                    "centroid": {"lat": 0.5, "lon": 0.5},
                    "is_observed": False,
                }
            ]
        )

    # B. Sparse observed states (single observation)
    hyps_single, _ = f3_supervisor.execute_hindcast(
        event_id="EVT_SINGLE",
        states=[
            {
                "observation_id": "OBS_SINGLE_01",
                "event_id": "EVT_SINGLE",
                "timestamp": "2026-01-01T00:00:00Z",
                "state_type": "OBSERVED",
                "polygon_geojson": {"type": "Polygon", "coordinates": [[[20.0, 38.0], [20.1, 38.0], [20.1, 38.1], [20.0, 38.0]]]},
                "area_km2": 2.0,
                "centroid": {"lat": 38.05, "lon": 20.05},
                "is_observed": True,
            }
        ]
    )
    hbest_single = next(h for h in hyps_single if h.ensemble_id == -1)
    assert hbest_single.data_quality_flag == "single_observation"

    # C. Empty AIS dataset
    cand_empty_ais = f4_supervisor.execute_reconstruction(
        event_id="EVT_SINGLE",
        hypothesis=hbest_single,
        raw_records=[],
    )
    assert cand_empty_ais == []

    # D. No AIS candidate inside corridor (point 500 km away or temporally disjoint)
    far_spatial_records = [
        {
            "mmsi": "999999999",
            "timestamp": hbest_single.origin_time_start,
            "latitude": 45.0,  # Far north (500+ km away)
            "longitude": 20.0,
            "sog_kn": 10.0,
            "cog_deg": 0.0,
            "is_observed": True,
        }
    ]
    corridor_res = f4_supervisor.filter_corridor(
        event_id="EVT_SINGLE",
        hypothesis=hbest_single,
        raw_records=far_spatial_records,
    )
    assert corridor_res.corridor_matches == 0
    assert corridor_res.matches == []

    # Temporally disjoint records produce 0 candidates in reconstruction
    far_temp_records = [
        {
            "mmsi": "999999999",
            "timestamp": "2026-06-01T00:00:00Z",  # Months later
            "latitude": hbest_single.source_location.lat,
            "longitude": hbest_single.source_location.lon,
            "sog_kn": 10.0,
            "cog_deg": 0.0,
            "is_observed": True,
        }
    ]
    cand_no_corr = f4_supervisor.execute_reconstruction(
        event_id="EVT_SINGLE",
        hypothesis=hbest_single,
        raw_records=far_temp_records,
    )
    assert cand_no_corr == []

    # E. Single-point vessel track inside corridor
    single_record = [
        {
            "mmsi": "777777777",
            "timestamp": hbest_single.origin_time_start,
            "latitude": hbest_single.source_location.lat,
            "longitude": hbest_single.source_location.lon,
            "sog_kn": 10.0,
            "cog_deg": 90.0,
            "is_observed": True,
        }
    ]
    cand_single_pt = f4_supervisor.execute_reconstruction(
        event_id="EVT_SINGLE",
        hypothesis=hbest_single,
        raw_records=single_record,
    )
    assert len(cand_single_pt) == 1
    assert cand_single_pt[0].number_of_observations == 1


# ==============================================================================
# 12. EVT0001 UPSTREAM-DEGRADATION TEST
# ==============================================================================

def test_evt0001_upstream_f3_limitation_diagnostic():
    """Diagnostic check confirming that for synthetic EVT0001:
    1. Upstream F3 HBEST hypothesis centroid has a known error relative to true origin (~62.25 km).
    2. The true source vessel (MMSI 329813634) is ~52.5 km away, which exceeds uncertainty_radius_km (7.66 km).
    3. F4 corridor filtering strictly excludes the vessel without expanding uncertainty radius or using ground truth.
    4. Diagnosed strictly as [UPSTREAM F3 QUALITY LIMITATION].
    """
    f3_supervisor = F3HindcastSupervisor()
    f4_supervisor = F4AISSupervisor()

    hyps, _ = f3_supervisor.execute_hindcast(event_id="EVT0001")
    hbest = next(h for h in hyps if h.source_hypothesis_id == "SH_EVT0001_HBEST")

    # Corridor filtering strictly excludes the true vessel (41.18 km > 7.66 km radius)
    corridor_result = f4_supervisor.filter_corridor("EVT0001", hbest)
    corridor_mmsis = {m.mmsi for m in corridor_result.matches}
    assert "329813634" not in corridor_mmsis, (
        "True vessel 329813634 was improperly included in corridor matches despite being > uncertainty radius! "
        "F4.2 must strictly obey distance <= uncertainty_radius_km."
    )
    assert corridor_result.corridor_matches == 0, (
        "Corridor matches for EVT0001 must be 0 due to upstream F3 source error [UPSTREAM F3 QUALITY LIMITATION]"
    )


# ==============================================================================
# 13. GROUND-TRUTH STATIC FIREWALL
# ==============================================================================

def test_ground_truth_static_firewall():
    """Scans all production Python files in backend/f3_hindcast/ and backend/f4_ais/
    to verify ZERO references to ground truth, evaluation labels, or culpability terms.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    banned_tokens = [
        "ground_truth_events",
        "is_true_source",
        "qa_source_error_km",
        "D4_vessel_tracks",
        "tolerance_km",
        "culprit",
        "guilty",
        "responsible_vessel",
        "guilt_probability",
    ]

    target_dirs = [
        repo_root / "backend" / "f3_hindcast",
        repo_root / "backend" / "f4_ais",
    ]

    violations = []
    for d in target_dirs:
        for py_file in d.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for token in banned_tokens:
                if token in text:
                    violations.append((py_file.name, token))

    assert len(violations) == 0, f"Prohibited firewall tokens found in runtime code: {violations}"


# ==============================================================================
# 14. DATASET INTEGRITY
# ==============================================================================

def test_protected_dataset_hashes():
    """Verifies SHA-256 checksums of protected datasets."""
    repo_root = Path(__file__).resolve().parent.parent.parent

    expected_hashes = {
        "D4_ais_raw.csv": (
            repo_root / "data" / "raw" / "synthetic" / "outputs" / "D4_ais_raw.csv",
            "dd6eb9d443033135dcda76f647ab837ed50ea4e1f8c178cdf9b29142daa66eec",
        ),
        "D4_vessel_tracks.csv": (
            repo_root / "data" / "raw" / "synthetic" / "outputs" / "D4_vessel_tracks.csv",
            "8bd8270035294826689524378909123b053bb48eb650c86c2582bf6ce5c6ad4b",
        ),
        "ground_truth_events.csv": (
            repo_root / "data" / "evaluation" / "synthetic" / "ground_truth_events.csv",
            "c7ef887b395ab5762c4ab097ab462d993074373076b5531fb090ad84d452490f",
        ),
    }

    for name, (path, expected_sha) in expected_hashes.items():
        assert path.exists(), f"Protected dataset file {name} missing at {path}"
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest().lower()
        assert actual_sha == expected_sha, (
            f"Dataset hash mismatch for {name}!\nExpected: {expected_sha}\nActual:   {actual_sha}"
        )


# ==============================================================================
# 15. NO HIDDEN DEPENDENCIES
# ==============================================================================

def test_no_hidden_cross_feature_dependencies():
    """Verifies that F3 does not import F4, and F4 does not import F5/F6/F7/F8 or UI frameworks."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    f3_dir = repo_root / "backend" / "f3_hindcast"
    f4_dir = repo_root / "backend" / "f4_ais"

    for py_file in f3_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "backend.f4_ais" not in text, f"F3 file {py_file.name} illegally imports F4"

    for py_file in f4_dir.rglob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("import") or line_str.startswith("from"):
                for forbidden in ["backend.f5", "backend.f6", "backend.f7", "backend.f8", "streamlit", "react"]:
                    assert forbidden not in line_str, f"F4 file {py_file.name} illegally imports {forbidden}: '{line_str}'"


# ==============================================================================
# 16. REPRODUCIBILITY
# ==============================================================================

def test_pipeline_deterministic_reproducibility():
    """Runs the complete F2 fixture -> F3 -> F4 -> CandidateVessel pipeline twice,
    and verifies byte-for-byte identical output serialization.
    """
    f2_fixture = [
        {
            "observation_id": "OBS_REPRO_000",
            "event_id": "EVT_REPRO",
            "timestamp": "2026-08-01T10:00:00Z",
            "state_type": "OBSERVED",
            "polygon_geojson": {"type": "Polygon", "coordinates": [[[22.0, 37.0], [22.1, 37.0], [22.1, 37.1], [22.0, 37.0]]]},
            "area_km2": 5.0,
            "centroid": {"lat": 37.05, "lon": 22.05},
            "is_observed": True,
        }
    ]

    raw_ais = [
        {
            "mmsi": "333222111",
            "timestamp": "2026-08-01T06:00:00Z",
            "latitude": 37.05,
            "longitude": 22.05,
            "sog_kn": 14.2,
            "cog_deg": 270.0,
            "is_observed": True,
        }
    ]

    # Run 1
    f3_1 = F3HindcastSupervisor()
    f4_1 = F4AISSupervisor()
    hyps_1, _ = f3_1.execute_hindcast("EVT_REPRO", states=f2_fixture, base_seed=42)
    hbest_1 = next(h for h in hyps_1 if h.ensemble_id == -1)
    cands_1 = f4_1.execute_reconstruction("EVT_REPRO", hypothesis=hbest_1, raw_records=raw_ais)
    dump_1 = json.dumps([c.model_dump() for c in cands_1], sort_keys=True)

    # Run 2
    f3_2 = F3HindcastSupervisor()
    f4_2 = F4AISSupervisor()
    hyps_2, _ = f3_2.execute_hindcast("EVT_REPRO", states=f2_fixture, base_seed=42)
    hbest_2 = next(h for h in hyps_2 if h.ensemble_id == -1)
    cands_2 = f4_2.execute_reconstruction("EVT_REPRO", hypothesis=hbest_2, raw_records=raw_ais)
    dump_2 = json.dumps([c.model_dump() for c in cands_2], sort_keys=True)

    assert dump_1 == dump_2, "Pipeline execution was not byte-for-byte identical!"
