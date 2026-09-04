"""Unit and integration tests for F4.2 — AIS Spatio-Temporal Corridor Filtering.

Validates:
- Tests A-W covering spatial, temporal, multi-hypothesis, preservation,
  boundary condition, determinism, and ground-truth isolation requirements.
- Full synthetic validation against D4_ais_raw.csv across multiple events.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.f4_ais.corridor import (
    CorridorFilteringService,
    haversine_distance_km,
    is_spatially_compatible,
    is_temporally_compatible,
)
from backend.f4_ais.ingestion import AISIngestionService
from backend.f4_ais.repository import F4Repository
from backend.f4_ais.router import router
from backend.f4_ais.schemas import (
    CorridorAISMatch,
    CorridorFilterResult,
    ValidatedAISFix,
)
from backend.f4_ais.supervisor import F4AISSupervisor
from shared.config.settings import get_settings
from shared.mocks.load_mock import load_mock
from shared.schemas.f3_contract import SourceHypothesisWindow


def _make_fix(
    mmsi: str = "244123456",
    timestamp: str = "2026-01-08T12:00:00Z",
    lat: float = 24.5,
    lon: float = 54.5,
    is_observed: bool = True,
    source: str = "TERRESTRIAL_AIS",
    sog_kn: float = 12.5,
    cog_deg: float = 180.0,
    heading_deg: float = 179.0,
    nav_status: str = "Under way using engine",
    vessel_type: str = "Tanker",
    vessel_length_m: float = 250.0,
    vessel_width_m: float = 44.0,
) -> ValidatedAISFix:
    """Helper to construct a valid ValidatedAISFix without event_id."""
    ts = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return ValidatedAISFix(
        mmsi=mmsi,
        timestamp_utc=ts,
        timestamp_iso=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        latitude=lat,
        longitude=lon,
        sog_kn=sog_kn,
        cog_deg=cog_deg,
        heading_deg=heading_deg,
        nav_status=nav_status,
        vessel_type=vessel_type,
        vessel_length_m=vessel_length_m,
        vessel_width_m=vessel_width_m,
        draught_m=12.0,
        source=source,
        is_observed=is_observed,
    )


def _make_hyp(
    event_id: str = "EVT0001",
    hyp_id: str = "SH_EVT0001_HBEST",
    lat: float = 24.5,
    lon: float = 54.5,
    t_start: str = "2026-01-08T10:00:00Z",
    t_end: str = "2026-01-08T14:00:00Z",
    radius_km: float = 10.0,
) -> SourceHypothesisWindow:
    """Helper to construct a valid SourceHypothesisWindow from F3 contract."""
    return SourceHypothesisWindow.model_validate({
        "source_hypothesis_id": hyp_id,
        "event_id": event_id,
        "source_location": {"lat": lat, "lon": lon},
        "origin_time_start": t_start,
        "origin_time_end": t_end,
        "uncertainty_radius_km": radius_km,
        "source_probability": 0.85,
    })


# ==============================================================================
# Requirement A: Valid source window accepted
# ==============================================================================
def test_requirement_a_valid_source_window_accepted():
    """Requirement A: SourceHypothesisWindow is consumed exactly without error."""
    hyp = _make_hyp()
    service = CorridorFilteringService()
    result = service.filter_corridor(fixes=[], hypothesis=hyp)
    assert result.event_id == "EVT0001"
    assert result.source_hypothesis_id == "SH_EVT0001_HBEST"
    assert result.corridor_matches == 0


# ==============================================================================
# Requirement B: AIS inside spatial radius included
# ==============================================================================
def test_requirement_b_spatial_inside_included():
    """Requirement B: Fix clearly inside uncertainty radius is retained."""
    hyp = _make_hyp(lat=24.500, lon=54.500, radius_km=10.0)
    # ~3.3 km north of source
    fix_inside = _make_fix(lat=24.530, lon=54.500, timestamp="2026-01-08T12:00:00Z")
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_inside], hyp)
    assert result.spatial_matches == 1
    assert result.corridor_matches == 1
    assert len(result.matches) == 1
    assert result.matches[0].distance_to_source_km < 10.0


# ==============================================================================
# Requirement C: AIS outside spatial radius excluded
# ==============================================================================
def test_requirement_c_spatial_outside_excluded():
    """Requirement C: Fix clearly outside uncertainty radius is excluded."""
    hyp = _make_hyp(lat=24.500, lon=54.500, radius_km=10.0)
    # ~22.2 km north of source (lat +0.2 deg)
    fix_outside = _make_fix(lat=24.700, lon=54.500, timestamp="2026-01-08T12:00:00Z")
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_outside], hyp)
    assert result.spatial_matches == 0
    assert result.corridor_matches == 0
    assert len(result.matches) == 0


# ==============================================================================
# Requirement D & E: Temporal before and after excluded
# ==============================================================================
def test_requirement_d_temporal_before_excluded():
    """Requirement D: Fix before origin_time_start is excluded."""
    hyp = _make_hyp(t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")
    fix_before = _make_fix(timestamp="2026-01-08T09:59:59Z")
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_before], hyp)
    assert result.spatial_matches == 1  # lat/lon matches
    assert result.temporal_matches == 0
    assert result.corridor_matches == 0


def test_requirement_e_temporal_after_excluded():
    """Requirement E: Fix after origin_time_end is excluded."""
    hyp = _make_hyp(t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")
    fix_after = _make_fix(timestamp="2026-01-08T14:00:01Z")
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_after], hyp)
    assert result.spatial_matches == 1
    assert result.temporal_matches == 0
    assert result.corridor_matches == 0


# ==============================================================================
# Requirement F & G: Boundary inclusion (start & end)
# ==============================================================================
def test_requirement_f_g_start_and_end_boundaries_included():
    """Requirements F & G: Timestamps exactly on origin_time_start and origin_time_end are included."""
    hyp = _make_hyp(t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")
    fix_start = _make_fix(mmsi="111111111", timestamp="2026-01-08T10:00:00Z")
    fix_end = _make_fix(mmsi="222222222", timestamp="2026-01-08T14:00:00Z")
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_start, fix_end], hyp)
    assert result.temporal_matches == 2
    assert result.corridor_matches == 2
    assert {m.mmsi for m in result.matches} == {"111111111", "222222222"}


# ==============================================================================
# Requirement H: UTC timezone consistency
# ==============================================================================
def test_requirement_h_utc_timezone_consistency():
    """Requirement H: Non-UTC or offset timestamps normalize consistently."""
    hyp = _make_hyp(t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")
    # Equivalent to 12:00:00 UTC represented with +04:00 offset (Gulf Standard Time)
    ts_gst = dt.datetime(2026, 1, 8, 16, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=4)))
    fix_offset = ValidatedAISFix(
        mmsi="333333333",
        timestamp_utc=ts_gst,
        timestamp_iso="2026-01-08T12:00:00Z",
        latitude=24.5,
        longitude=54.5,
        source="TERRESTRIAL_AIS",
        is_observed=True,
    )
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_offset], hyp)
    assert result.temporal_matches == 1
    assert result.corridor_matches == 1
    assert result.matches[0].timestamp_utc.tzinfo == dt.timezone.utc


# ==============================================================================
# Requirement I & J: Multi-hypothesis handling & same fix matching multiple hypotheses
# ==============================================================================
def test_requirement_i_j_multiple_hypotheses_and_dual_match():
    """Requirements I & J:
    - Multiple hypotheses are processed independently.
    - One AIS fix matching two overlapping hypotheses produces two corridor matches
      with distinct source_hypothesis_id, never collapsed.
    """
    hyp1 = _make_hyp(event_id="EVT0001", hyp_id="SH_EVT0001_00", lat=24.50, lon=54.50, radius_km=15.0)
    hyp2 = _make_hyp(event_id="EVT0001", hyp_id="SH_EVT0001_01", lat=24.55, lon=54.55, radius_km=15.0)
    
    # Fix located at (24.52, 54.52) falls inside both hypotheses
    shared_fix = _make_fix(mmsi="444444444", lat=24.52, lon=54.52, timestamp="2026-01-08T12:00:00Z")
    
    service = CorridorFilteringService()
    results = service.filter_multiple_hypotheses([shared_fix], [hyp1, hyp2])
    
    assert len(results) == 2
    res1 = results["SH_EVT0001_00"]
    res2 = results["SH_EVT0001_01"]
    assert res1.source_hypothesis_id == "SH_EVT0001_00"
    assert res2.source_hypothesis_id == "SH_EVT0001_01"
    assert res1.corridor_matches == 1
    assert res2.corridor_matches == 1
    
    # Verify matches preserve separate hypothesis IDs
    assert res1.matches[0].source_hypothesis_id == "SH_EVT0001_00"
    assert res2.matches[0].source_hypothesis_id == "SH_EVT0001_01"


# ==============================================================================
# Requirement K & L: Event association from SourceHypothesisWindow, not raw AIS
# ==============================================================================
def test_requirement_k_l_event_association_origin():
    """Requirements K & L:
    - Raw ValidatedAISFix does NOT contain event_id.
    - Event association is solely conferred by the matching SourceHypothesisWindow.
    """
    fix = _make_fix(mmsi="555555555")
    assert not hasattr(fix, "event_id")
    
    hyp = _make_hyp(event_id="EVT0042", hyp_id="SH_EVT0042_HBEST")
    service = CorridorFilteringService()
    result = service.filter_corridor([fix], hyp)
    
    assert result.event_id == "EVT0042"
    assert len(result.matches) == 1
    assert result.matches[0].event_id == "EVT0042"
    assert result.matches[0].source_hypothesis_id == "SH_EVT0042_HBEST"


# ==============================================================================
# Requirement M & N: Preservation of is_observed and source
# ==============================================================================
def test_requirement_m_n_is_observed_and_source_preserved():
    """Requirements M & N:
    - is_observed is preserved exactly (True or False), not reinterpreted.
    - source (e.g. SATELLITE_AIS) is preserved verbatim.
    """
    fix_unobserved = _make_fix(
        mmsi="666666666",
        is_observed=False,
        source="SATELLITE_AIS",
    )
    hyp = _make_hyp()
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_unobserved], hyp)
    
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.is_observed is False
    assert match.source == "SATELLITE_AIS"


# ==============================================================================
# Requirement O: Valid position with missing navigation retained
# ==============================================================================
def test_requirement_o_missing_navigation_retained():
    """Requirement O: Fix with missing SOG, COG, heading, nav_status is retained."""
    fix_sparse_nav = ValidatedAISFix(
        mmsi="777777777",
        timestamp_utc=dt.datetime(2026, 1, 8, 12, 0, 0, tzinfo=dt.timezone.utc),
        timestamp_iso="2026-01-08T12:00:00Z",
        latitude=24.5,
        longitude=54.5,
        sog_kn=None,
        cog_deg=None,
        heading_deg=None,
        nav_status=None,
        vessel_type=None,
        vessel_length_m=None,
        vessel_width_m=None,
        draught_m=None,
        source="TERRESTRIAL_AIS",
        is_observed=True,
    )
    hyp = _make_hyp()
    service = CorridorFilteringService()
    result = service.filter_corridor([fix_sparse_nav], hyp)
    
    assert result.corridor_matches == 1
    m = result.matches[0]
    assert m.sog_kn is None
    assert m.cog_deg is None
    assert m.heading_deg is None
    assert m.nav_status is None


# ==============================================================================
# Requirement P & Q: Empty & sparse AIS handled gracefully
# ==============================================================================
def test_requirement_p_q_empty_and_sparse_ais_handling():
    """Requirements P & Q:
    - Empty AIS input returns deterministic result without exception.
    - Sparse AIS with zero corridor matches returns empty result with diagnostic counts.
    """
    hyp = _make_hyp()
    service = CorridorFilteringService()
    
    # Completely empty
    res_empty = service.filter_corridor([], hyp)
    assert res_empty.total_ais_input == 0
    assert res_empty.spatial_matches == 0
    assert res_empty.temporal_matches == 0
    assert res_empty.corridor_matches == 0
    assert res_empty.matches == []
    
    # Sparse: fix matches temporally but not spatially
    fix_far = _make_fix(lat=50.0, lon=0.0, timestamp="2026-01-08T12:00:00Z")
    res_sparse = service.filter_corridor([fix_far], hyp)
    assert res_sparse.total_ais_input == 1
    assert res_sparse.spatial_matches == 0
    assert res_sparse.temporal_matches == 1
    assert res_sparse.corridor_matches == 0
    assert res_sparse.matches == []


# ==============================================================================
# Requirement R: Deterministic output ordering
# ==============================================================================
def test_requirement_r_deterministic_output_ordering():
    """Requirement R: Corridor matches are sorted deterministically by (event_id, hyp_id, mmsi, timestamp_iso)."""
    hyp = _make_hyp(radius_km=50.0)
    fixes = [
        _make_fix(mmsi="999999999", timestamp="2026-01-08T13:00:00Z"),
        _make_fix(mmsi="111111111", timestamp="2026-01-08T12:00:00Z"),
        _make_fix(mmsi="111111111", timestamp="2026-01-08T11:00:00Z"),
        _make_fix(mmsi="555555555", timestamp="2026-01-08T12:30:00Z"),
    ]
    service = CorridorFilteringService()
    res1 = service.filter_corridor(fixes, hyp)
    # Reverse input order to test stability
    res2 = service.filter_corridor(list(reversed(fixes)), hyp)
    
    assert [m.mmsi for m in res1.matches] == ["111111111", "111111111", "555555555", "999999999"]
    assert [m.timestamp_iso for m in res1.matches[:2]] == ["2026-01-08T11:00:00Z", "2026-01-08T12:00:00Z"]
    assert [m.mmsi for m in res1.matches] == [m.mmsi for m in res2.matches]
    assert [m.timestamp_iso for m in res1.matches] == [m.timestamp_iso for m in res2.matches]


# ==============================================================================
# Requirement S: Geodesic distance sanity checks (haversine)
# ==============================================================================
def test_requirement_s_geodesic_distance_sanity():
    """Requirement S:
    - Verifies haversine distance accuracy across equator, meridians, and longitude boundaries.
    - Confirms proper spherical geometry, rejecting naive Euclidean distance.
    """
    # 1. Equator: 1 degree longitude at equator ~= 111.195 km (2 * pi * 6371 / 360)
    d_eq = haversine_distance_km(0.0, 0.0, 0.0, 1.0)
    expected_1deg = 2.0 * math.pi * 6371.0 / 360.0
    assert abs(d_eq - expected_1deg) < 0.01
    
    # 2. Meridian: 1 degree latitude ~= 111.195 km
    d_lat = haversine_distance_km(0.0, 0.0, 1.0, 0.0)
    assert abs(d_lat - expected_1deg) < 0.01
    
    # 3. High latitude: 1 degree longitude at 60 deg lat ~= 55.6 km (cos(60) = 0.5)
    d_60 = haversine_distance_km(60.0, 0.0, 60.0, 1.0)
    assert abs(d_60 - (expected_1deg * 0.5)) < 0.2
    
    # 4. Longitude antimeridian wrap: 179.9 E to -179.9 W is 0.2 deg apart
    d_wrap = haversine_distance_km(0.0, 179.9, 0.0, -179.9)
    assert abs(d_wrap - (expected_1deg * 0.2)) < 0.05
    
    # 5. Spatial boundary check: exact radius is included
    compat_exact, dist_exact = is_spatially_compatible(0.0, 0.0, 0.0, 1.0, uncertainty_radius_km=d_eq)
    assert compat_exact is True
    assert dist_exact == d_eq

    # 6. Point just outside uncertainty radius is excluded (no tolerance)
    compat_outside, dist_outside = is_spatially_compatible(0.0, 0.0, 0.0, 1.0, uncertainty_radius_km=d_eq - 0.0001)
    assert compat_outside is False
    assert dist_outside > (d_eq - 0.0001)


def test_spatial_boundary_strict_no_tolerance():
    """Explicitly verifies strict spatial boundary rules:
    - Point inside uncertainty radius -> included
    - Point exactly at uncertainty radius -> included
    - Point just outside uncertainty radius -> excluded
    - No tolerance or spatial buffer is applied
    """
    src_lat, src_lon = 24.0, 54.0
    fix_lat, fix_lon = 24.0, 55.0
    exact_dist = haversine_distance_km(fix_lat, fix_lon, src_lat, src_lon)
    
    # Point inside uncertainty radius -> included
    compat_in, _ = is_spatially_compatible(fix_lat, fix_lon, src_lat, src_lon, uncertainty_radius_km=exact_dist + 0.1)
    assert compat_in is True
    
    # Point exactly at uncertainty radius -> included
    compat_boundary, _ = is_spatially_compatible(fix_lat, fix_lon, src_lat, src_lon, uncertainty_radius_km=exact_dist)
    assert compat_boundary is True
    
    # Point just outside uncertainty radius (by 0.0001 km / 10 cm) -> excluded
    compat_out, _ = is_spatially_compatible(fix_lat, fix_lon, src_lat, src_lon, uncertainty_radius_km=exact_dist - 0.0001)
    assert compat_out is False
    
    # Verify CorridorFilteringService enforces the same strict boundary
    service = CorridorFilteringService()
    fix = _make_fix(lat=fix_lat, lon=fix_lon)
    
    hyp_boundary = _make_hyp(lat=src_lat, lon=src_lon, radius_km=exact_dist)
    res_boundary = service.filter_corridor([fix], hyp_boundary)
    assert res_boundary.spatial_matches == 1
    assert res_boundary.corridor_matches == 1
    
    hyp_out = _make_hyp(lat=src_lat, lon=src_lon, radius_km=exact_dist - 0.0001)
    res_out = service.filter_corridor([fix], hyp_out)
    assert res_out.spatial_matches == 0
    assert res_out.corridor_matches == 0


# ==============================================================================
# Requirement T & U: Ground-truth isolation & no D4_vessel_tracks runtime dependency
# ==============================================================================
def test_requirement_t_u_no_ground_truth_or_tracks_dependency():
    """Requirements T & U:
    - Verifies that no F4.2 runtime source code imports or references:
      ground_truth_events, is_true_source, qa_source_error_km, or D4_vessel_tracks.
    """
    f4_dir = Path("backend/f4_ais")
    banned_tokens = [
        "ground_truth_events",
        "is_true_source",
        "qa_source_error_km",
        "D4_vessel_tracks",
    ]
    
    py_files = list(f4_dir.glob("*.py"))
    assert len(py_files) > 0, "Expected Python files in backend/f4_ais"
    
    for pf in py_files:
        content = pf.read_text(encoding="utf-8")
        for token in banned_tokens:
            assert token not in content, f"Found banned token '{token}' in runtime file: {pf}"


# ==============================================================================
# Requirement V & W: F4.0 and F4.1 regression
# ==============================================================================
def test_requirement_v_w_regression():
    """Requirements V & W:
    - Verifies F4.0 supervisor and F4.1 ingestion agent continue functioning correctly.
    """
    supervisor = F4AISSupervisor()
    candidates = supervisor.execute_reconstruction("EVT0001")
    assert isinstance(candidates, list)
    
    # Ingestion agent regression
    ingestion = AISIngestionService()
    fixes, report = ingestion.ingest_csv(get_settings().D4_AIS_RAW_CSV_PATH)
    assert len(fixes) > 0
    assert report.total_records == len(fixes)


# ==============================================================================
# API & Repository Integration Test
# ==============================================================================
def test_api_corridor_filter_endpoint():
    """Verifies POST /api/v1/f4/corridor-filter/{event_id} endpoint and envelope."""
    app = FastAPI(title="F4 Test App")
    app.include_router(router)
    client = TestClient(app)
    
    resp = client.post("/api/v1/f4/corridor-filter/EVT0001")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    data = body["data"]
    assert data["event_id"] == "EVT0001"
    assert "total_ais_input" in data
    assert "spatial_matches" in data
    assert "temporal_matches" in data
    assert "corridor_matches" in data


# ==============================================================================
# Requirement X: Full Synthetic Dataset Validation (D4_ais_raw.csv across events)
# ==============================================================================
def test_requirement_x_synthetic_dataset_validation():
    """Requirement X: Full validation against actual D4_ais_raw.csv (29,407 records).
    
    Evaluates corridor filtering on actual F3 source hypothesis windows across multiple events.
    Verifies deterministic counts, graceful sparse handling, and contract conformance.
    """
    csv_path = get_settings().D4_AIS_RAW_CSV_PATH
    assert csv_path.exists(), f"Dataset file missing: {csv_path}"
    
    ingestion = AISIngestionService()
    fixes, report = ingestion.ingest_csv(csv_path)
    assert len(fixes) == 29407
    
    service = CorridorFilteringService()
    
    # Test across events EVT0001, EVT0002, EVT0003
    for evt_id in ["EVT0001", "EVT0002", "EVT0003"]:
        f3_hypotheses = load_mock("f3", evt_id)
        assert len(f3_hypotheses) > 0
        
        # Test each hypothesis
        for hyp_dict in f3_hypotheses:
            hyp = SourceHypothesisWindow.model_validate(hyp_dict)
            result = service.filter_corridor(fixes, hyp)
            
            # Assert schema validity
            assert result.event_id == evt_id
            assert result.source_hypothesis_id == hyp.source_hypothesis_id
            assert result.total_ais_input == 29407
            assert result.spatial_matches >= 0
            assert result.temporal_matches >= 0
            assert result.corridor_matches == len(result.matches)
            
            # For each match, verify constraints
            for m in result.matches:
                assert m.event_id == evt_id
                assert m.source_hypothesis_id == hyp.source_hypothesis_id
                assert m.distance_to_source_km <= hyp.uncertainty_radius_km
                assert hyp.origin_time_start <= m.timestamp_utc <= hyp.origin_time_end


def test_corridor_filtering_agent_and_alias():
    """Verifies CorridorFilteringAgent operates identically and CandidateFilteringAgent alias exists."""
    from backend.f4_ais.agents import CandidateFilteringAgent, CorridorFilteringAgent

    agent = CorridorFilteringAgent()
    hyp = _make_hyp()
    fix = _make_fix()
    res = agent.filter_corridor([fix], hyp)
    assert res.corridor_matches == 1

    # Verify alias works
    assert CandidateFilteringAgent is CorridorFilteringAgent
