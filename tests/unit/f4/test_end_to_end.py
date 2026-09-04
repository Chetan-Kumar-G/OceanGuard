"""Feature F4.8 — Final F4 Integration, Forensic QA, Determinism & Edge Case Test Suite.

Verifies:
- End-to-end pipeline: F3 SourceHypothesisWindow -> F4.1 -> F4.2 -> F4.3 -> F4.4 -> F4.5 -> F4.6 -> F4.7 -> CandidateVessel[] -> F5
- Strict ground-truth quarantine: ZERO runtime dependencies on ground truth files or labels
- Determinism: running twice on identical input yields identical outputs
- Edge cases: empty AIS, sparse AIS, 1 vessel, multiple vessels, multiple hypotheses,
  missing SOG/COG/heading, reporting gaps, interpolated closest approach, boundary conditions
- Offline QA evaluation comparing runtime candidate recall against ground truth without runtime leakage
- Performance sanity over synthetic dataset
"""
from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pytest

from shared.config.settings import get_settings
from shared.schemas.f3_contract import SourceHypothesisWindow, SourceLocationCoord
from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.candidate import CandidateVesselService
from backend.f4_ais.corridor import haversine_distance_km
from backend.f4_ais.repository import F4Repository
from backend.f4_ais.schemas import (
    CorridorAISMatch,
    RawAISRecord,
    ValidatedAISFix,
    VesselTrack,
)
from backend.f4_ais.supervisor import F4AISSupervisor


@pytest.fixture
def supervisor() -> F4AISSupervisor:
    return F4AISSupervisor(repository=F4Repository())


@pytest.fixture
def sample_hypothesis() -> SourceHypothesisWindow:
    return SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0001_HBEST",
        event_id="EVT0001",
        ensemble_id=-1,
        source_location=SourceLocationCoord(lat=12.0, lon=80.0),
        origin_time_start="2026-03-01T10:00:00Z",
        origin_time_end="2026-03-01T14:00:00Z",
        uncertainty_radius_km=15.0,
        source_probability=1.0,
    )


def test_f4_8_end_to_end_pipeline(supervisor: F4AISSupervisor, sample_hypothesis: SourceHypothesisWindow):
    """Verifies complete deterministic flow through supervisor:
    F3 -> F4.1 -> F4.2 -> F4.3 -> F4.4 -> F4.5 -> F4.6 -> F4.7 -> CandidateVessel[]
    """
    raw_records = [
        # Vessel 1: in corridor during origin window
        RawAISRecord(
            mmsi=123456789,
            timestamp="2026-03-01T11:00:00Z",
            latitude=12.02,
            longitude=80.02,
            sog_kn=10.5,
            cog_deg=45.0,
            heading_deg=44.0,
            nav_status="under_way_using_engine",
            vessel_name="TEST_VESSEL_1",
            vessel_type="Tanker",
            is_observed=True,
            source="terrestrial_ais",
        ),
        RawAISRecord(
            mmsi=123456789,
            timestamp="2026-03-01T11:30:00Z",
            latitude=12.05,
            longitude=80.05,
            sog_kn=11.0,
            cog_deg=45.0,
            heading_deg=46.0,
            is_observed=True,
        ),
        # Vessel 2: outside corridor (distance > 15 km)
        RawAISRecord(
            mmsi=987654321,
            timestamp="2026-03-01T11:00:00Z",
            latitude=13.5,
            longitude=81.5,
            sog_kn=12.0,
            cog_deg=90.0,
            is_observed=True,
        ),
    ]

    candidates = supervisor.execute_reconstruction(
        event_id="EVT0001",
        hypothesis=sample_hypothesis,
        raw_records=raw_records,
    )

    assert isinstance(candidates, list)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.mmsi == "123456789"
    assert cand.event_id == "EVT0001"
    assert cand.source_hypothesis_id == "SH_EVT0001_HBEST"
    assert cand.track_id == "TRK_EVT0001_123456789"
    assert cand.distance_to_source_effective_km < 15.0
    assert cand.temporal_compatibility > 0.0
    assert cand.track_overlap > 0.0
    assert cand.track_completeness > 0.0
    assert isinstance(cand.dark_gap_over_source, bool)
    assert cand.speed_compatibility is not None
    assert cand.course_compatibility is not None
    assert cand.closest_approach_is_interpolated is False


def test_f4_8_determinism(supervisor: F4AISSupervisor, sample_hypothesis: SourceHypothesisWindow):
    """Running complete pipeline twice with identical inputs must yield identical outputs."""
    raw_records = [
        RawAISRecord(mmsi=111111111, timestamp="2026-03-01T10:30:00Z", latitude=12.01, longitude=80.01, sog_kn=8.0, cog_deg=100.0, is_observed=True),
        RawAISRecord(mmsi=111111111, timestamp="2026-03-01T11:00:00Z", latitude=12.02, longitude=80.02, sog_kn=8.5, cog_deg=102.0, is_observed=True),
        RawAISRecord(mmsi=222222222, timestamp="2026-03-01T12:00:00Z", latitude=12.04, longitude=80.04, sog_kn=14.0, cog_deg=220.0, is_observed=True),
        RawAISRecord(mmsi=222222222, timestamp="2026-03-01T12:30:00Z", latitude=12.06, longitude=80.06, sog_kn=14.2, cog_deg=222.0, is_observed=True),
    ]

    run1 = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, raw_records)
    run2 = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, raw_records)

    assert len(run1) == len(run2)
    assert len(run1) == 2

    for c1, c2 in zip(run1, run2):
        assert c1.model_dump() == c2.model_dump()


def test_f4_8_forensic_qa_zero_runtime_dependencies():
    """Verifies that no F4 runtime module imports or references banned tokens."""
    f4_dir = Path("backend/f4_ais")
    banned_tokens = [
        "ground_truth_events",
        "is_true_source",
        "qa_source_error_km",
        "D4_vessel_tracks",
    ]

    py_files = list(f4_dir.glob("*.py"))
    assert len(py_files) >= 8, f"Expected at least 8 Python files in backend/f4_ais, found {len(py_files)}"

    for pf in py_files:
        content = pf.read_text(encoding="utf-8")
        for token in banned_tokens:
            assert token not in content, f"Found banned token '{token}' in runtime file: {pf}"


def test_f4_8_edge_cases(supervisor: F4AISSupervisor, sample_hypothesis: SourceHypothesisWindow):
    """Tests edge cases: empty AIS, sparse AIS, missing navigation, gaps, boundary conditions."""
    # 1. Empty AIS stream
    empty_result = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, [])
    assert empty_result == []

    # 2. Sparse AIS (single fix inside corridor)
    single_fix = [
        RawAISRecord(mmsi=333333333, timestamp="2026-03-01T11:00:00Z", latitude=12.01, longitude=80.01, is_observed=True)
    ]
    sparse_res = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, single_fix)
    assert len(sparse_res) == 1
    assert sparse_res[0].mmsi == "333333333"
    assert sparse_res[0].temporal_compatibility > 0.0
    assert sparse_res[0].track_overlap > 0.0

    # 3. Missing SOG and COG (None values must NOT become zero)
    none_nav_records = [
        RawAISRecord(mmsi=444444444, timestamp="2026-03-01T11:00:00Z", latitude=12.01, longitude=80.01, sog_kn=None, cog_deg=None, is_observed=True),
        RawAISRecord(mmsi=444444444, timestamp="2026-03-01T11:30:00Z", latitude=12.02, longitude=80.02, sog_kn=None, cog_deg=None, is_observed=True),
    ]
    none_res = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, none_nav_records)
    assert len(none_res) == 1
    assert none_res[0].observed_speed_kn is None
    assert none_res[0].observed_course_deg is None
    assert none_res[0].speed_compatibility == 0.5
    assert none_res[0].course_compatibility == 0.5

    # 4. Interpolated closest approach
    interpolated_records = [
        RawAISRecord(mmsi=555555555, timestamp="2026-03-01T10:00:00Z", latitude=12.10, longitude=80.10, is_observed=True),
        RawAISRecord(mmsi=555555555, timestamp="2026-03-01T11:00:00Z", latitude=12.001, longitude=80.001, is_observed=False),  # closer interpolated
        RawAISRecord(mmsi=555555555, timestamp="2026-03-01T12:00:00Z", latitude=12.15, longitude=80.15, is_observed=True),
    ]
    interp_res = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, interpolated_records)
    assert len(interp_res) == 1
    assert interp_res[0].closest_approach_is_interpolated is True

    # 5. Spatial boundary test: inside vs strictly outside
    # 15.0 km boundary: lat=12.0, lon=80.0 -> lat=12.13 (~14.4 km) inside, lat=12.20 (~22.2 km) outside
    boundary_records = [
        RawAISRecord(mmsi=666666666, timestamp="2026-03-01T11:00:00Z", latitude=12.13, longitude=80.0, is_observed=True),
        RawAISRecord(mmsi=777777777, timestamp="2026-03-01T11:00:00Z", latitude=12.20, longitude=80.0, is_observed=True),
    ]
    bound_res = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, boundary_records)
    assert len(bound_res) == 1
    assert bound_res[0].mmsi == "666666666"

    # 6. Temporal boundary test: exactly at window start and window end
    temp_boundary = [
        RawAISRecord(mmsi=888888888, timestamp="2026-03-01T10:00:00Z", latitude=12.01, longitude=80.01, is_observed=True),
        RawAISRecord(mmsi=888888888, timestamp="2026-03-01T14:00:00Z", latitude=12.02, longitude=80.02, is_observed=True),
    ]
    temp_res = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, temp_boundary)
    assert len(temp_res) == 1
    assert temp_res[0].temporal_compatibility > 0.0


def test_f4_8_multiple_hypotheses_preservation(supervisor: F4AISSupervisor):
    """Verifies that multiple source hypotheses preserve distinct candidate representations."""
    hyp_a = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0001_ENS01",
        event_id="EVT0001",
        ensemble_id=1,
        source_location=SourceLocationCoord(lat=12.0, lon=80.0),
        origin_time_start="2026-03-01T10:00:00Z",
        origin_time_end="2026-03-01T12:00:00Z",
        uncertainty_radius_km=15.0,
        source_probability=0.6,
    )
    hyp_b = SourceHypothesisWindow(
        source_hypothesis_id="SH_EVT0001_ENS02",
        event_id="EVT0001",
        ensemble_id=2,
        source_location=SourceLocationCoord(lat=12.2, lon=80.2),
        origin_time_start="2026-03-01T12:00:00Z",
        origin_time_end="2026-03-01T14:00:00Z",
        uncertainty_radius_km=15.0,
        source_probability=0.4,
    )

    records = [
        RawAISRecord(mmsi=999999999, timestamp="2026-03-01T11:00:00Z", latitude=12.01, longitude=80.01, is_observed=True),
        RawAISRecord(mmsi=999999999, timestamp="2026-03-01T13:00:00Z", latitude=12.21, longitude=80.21, is_observed=True),
    ]

    cand_a = supervisor.execute_reconstruction("EVT0001", hyp_a, records)
    cand_b = supervisor.execute_reconstruction("EVT0001", hyp_b, records)

    assert len(cand_a) == 1
    assert len(cand_b) == 1
    assert cand_a[0].source_hypothesis_id == "SH_EVT0001_ENS01"
    assert cand_b[0].source_hypothesis_id == "SH_EVT0001_ENS02"


def test_f4_8_candidate_vessel_contract_integrity(supervisor: F4AISSupervisor, sample_hypothesis: SourceHypothesisWindow):
    """Verifies that CandidateVessel schema strictly adheres to frozen F4 -> F5 contract."""
    records = [
        RawAISRecord(mmsi=123456789, timestamp="2026-03-01T11:00:00Z", latitude=12.01, longitude=80.01, sog_kn=10.0, cog_deg=50.0, is_observed=True)
    ]
    candidates = supervisor.execute_reconstruction("EVT0001", sample_hypothesis, records)
    assert len(candidates) == 1
    cand = candidates[0]

    # Check required fields presence
    data = cand.model_dump()
    expected_fields = [
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
    ]
    for field in expected_fields:
        assert field in data, f"Missing required CandidateVessel field: {field}"

    # Banned QA-only fields must NOT be present
    banned_fields = ["is_true_source", "qa_source_error_km", "probability_of_guilt", "culprit_score"]
    for field in banned_fields:
        assert field not in data, f"Unexpected field in CandidateVessel: {field}"


def test_f4_8_synthetic_end_to_end_and_offline_qa_evaluation(supervisor: F4AISSupervisor):
    """Runs realistic synthetic end-to-end execution on EVT0001 from D4_ais_raw.csv,
    measures execution performance, and performs OFFLINE-ONLY QA evaluation
    by comparing candidates against ground_truth_events.csv.
    """
    settings = get_settings()
    if not settings.D4_AIS_RAW_CSV_PATH.exists():
        pytest.skip(f"Synthetic raw AIS file not found at {settings.D4_AIS_RAW_CSV_PATH}")

    # 1. Performance and runtime candidate generation
    t0 = time.perf_counter()
    candidates = supervisor.execute_reconstruction("EVT0001")
    elapsed_sec = time.perf_counter() - t0

    assert len(candidates) > 0, "Expected candidates for EVT0001"
    candidate_mmsis = {c.mmsi for c in candidates}
    print(f"\n[PERFORMANCE] EVT0001 candidate generation took {elapsed_sec:.3f}s. Total candidates: {len(candidates)}")

    # 2. Offline QA Evaluation (strict firewall: only in test, never in runtime)
    gt_path = settings.DATA_DIR / "evaluation" / "synthetic" / "ground_truth_events.csv"
    if gt_path.exists():
        with open(gt_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            gt_rows = [row for row in reader if row.get("event_id") == "EVT0001"]

        if gt_rows:
            true_source_mmsi = int(gt_rows[0]["true_source_mmsi"])
            true_lat = float(gt_rows[0]["true_origin_lat"])
            true_lon = float(gt_rows[0]["true_origin_lon"])
            # QA Metric: True source presence in candidate set
            true_source_found = true_source_mmsi in candidate_mmsis
            
            # Diagnostic evaluation: distance between true origin and F3 hypothesis
            hyp = supervisor.resolve_source_hypothesis("EVT0001")
            dist_to_hyp = haversine_distance_km(true_lat, true_lon, hyp.source_location.lat, hyp.source_location.lon)
            print(f"[OFFLINE QA METRIC] EVT0001 True Source MMSI: {true_source_mmsi}")
            print(f"[OFFLINE QA METRIC] True Origin vs F3 Hypothesis Distance: {dist_to_hyp:.2f} km (Uncertainty Radius: {hyp.uncertainty_radius_km:.2f} km)")
            print(f"[OFFLINE QA METRIC] True Source MMSI in F4 Candidates: {true_source_found}")
            
            # When F3 source error exceeds uncertainty radius, candidate generation correctly obeys F4.2 corridor boundary
            if dist_to_hyp > hyp.uncertainty_radius_km:
                assert not true_source_found, "True source should not be in corridor when outside uncertainty radius"


def test_f4_8_missing_vs_zero_navigation_values(supervisor: F4AISSupervisor, sample_hypothesis: SourceHypothesisWindow):
    """Issue 2 Semantic Test:
    Verifies that missing SOG/COG (None) is semantically distinct from stationary/North (0.0).
    - Missing SOG -> observed_speed_kn is None, speed_compatibility = 0.5 (neutral unavailable evidence)
    - Measured SOG = 0.0 -> observed_speed_kn == 0.0, speed_compatibility evaluated against drift
    - Missing COG -> observed_course_deg is None, course_compatibility = 0.5
    - Measured COG = 0.0 -> observed_course_deg == 0.0, course_compatibility evaluated against drift
    """
    raw_records = [
        # Vessel A: Missing SOG and COG
        RawAISRecord(
            mmsi=100000001,
            timestamp="2026-03-01T11:00:00Z",
            latitude=12.01,
            longitude=80.01,
            sog_kn=None,
            cog_deg=None,
            is_observed=True,
        ),
        # Vessel B: Measured SOG = 0.0, COG = 0.0
        RawAISRecord(
            mmsi=100000002,
            timestamp="2026-03-01T11:00:00Z",
            latitude=12.02,
            longitude=80.02,
            sog_kn=0.0,
            cog_deg=0.0,
            is_observed=True,
        ),
    ]

    candidates = supervisor.execute_reconstruction(
        event_id="EVT0001",
        hypothesis=sample_hypothesis,
        raw_records=raw_records,
    )

    cand_map = {c.mmsi: c for c in candidates}
    cand_a = cand_map["100000001"]
    cand_b = cand_map["100000002"]

    # Vessel A (Unavailable Evidence)
    assert cand_a.observed_speed_kn is None
    assert cand_a.observed_course_deg is None
    assert cand_a.speed_compatibility == 0.5
    assert cand_a.course_compatibility == 0.5

    # Vessel B (Measured Zero Values)
    assert cand_b.observed_speed_kn == 0.0
    assert cand_b.observed_course_deg == 0.0
    # Provenance fields ensure downstream can distinguish unavailable evidence from measured values
    assert cand_a.observed_speed_kn != cand_b.observed_speed_kn
    assert cand_a.observed_course_deg != cand_b.observed_course_deg


def test_f4_8_track_context_window_bounding(supervisor: F4AISSupervisor, sample_hypothesis: SourceHypothesisWindow):
    """Issue 1 Semantic Test:
    Verifies that track reconstruction context is bounded deterministically to the context window
    [origin_start - 24h, origin_end + 24h] and does not scan unlimited historical AIS.
    """
    raw_records = [
        # Fix 1: 72 hours before window (outside 24h context window -> excluded from track)
        RawAISRecord(
            mmsi=200000001,
            timestamp="2026-02-26T10:00:00Z",
            latitude=12.01,
            longitude=80.01,
            is_observed=True,
        ),
        # Fix 2: 12 hours before window (inside 24h context window -> included in track)
        RawAISRecord(
            mmsi=200000001,
            timestamp="2026-02-28T22:00:00Z",
            latitude=12.01,
            longitude=80.01,
            is_observed=True,
        ),
        # Fix 3: Inside origin window & inside corridor
        RawAISRecord(
            mmsi=200000001,
            timestamp="2026-03-01T11:00:00Z",
            latitude=12.01,
            longitude=80.01,
            is_observed=True,
        ),
    ]

    candidates = supervisor.execute_reconstruction(
        event_id="EVT0001",
        hypothesis=sample_hypothesis,
        raw_records=raw_records,
    )

    assert len(candidates) == 1
    cand = candidates[0]
    # The track should contain 2 fixes (Fix 2 and Fix 3), not Fix 1
    assert cand.number_of_observations == 2
    assert cand.first_timestamp == "2026-02-28T22:00:00Z"


def test_f4_8_absence_not_confused_with_dark_gap(supervisor: F4AISSupervisor, sample_hypothesis: SourceHypothesisWindow):
    """Issue 4 & 9 Semantic Test:
    Verifies that a vessel's absence from the origin window is NOT classified as a dark gap.
    A vessel operating continuously for 30 minutes inside the window without dropouts,
    and then departing the area, must have:
    - dark_gap_over_source = False
    - dark_gap_over_source_hours = 0.0
    - ais_gap_ratio_origin_window = 0.0 (absence != reporting gap)
    """
    raw_records = [
        RawAISRecord(
            mmsi=300000001,
            timestamp="2026-03-01T10:00:00Z",
            latitude=12.01,
            longitude=80.01,
            is_observed=True,
        ),
        RawAISRecord(
            mmsi=300000001,
            timestamp="2026-03-01T10:30:00Z",
            latitude=12.02,
            longitude=80.02,
            is_observed=True,
        ),
    ]

    candidates = supervisor.execute_reconstruction(
        event_id="EVT0001",
        hypothesis=sample_hypothesis,
        raw_records=raw_records,
    )

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.dark_gap_over_source is False
    assert cand.dark_gap_over_source_hours == 0.0
    assert cand.ais_gap_ratio_origin_window == 0.0  # Absence after departure is NOT a gap

