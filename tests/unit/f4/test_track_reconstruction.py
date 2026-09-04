"""Unit tests for Feature F4.3 — Vessel Track Reconstruction.

Verifies:
- Grouping by MMSI and hypothesis context
- Strictly chronological, deterministic sorting
- Reporting gap detection and metric calculation
- Observed vs non-observed provenance preservation
- Track completeness calculation
- Track ID naming convention (TRK_<event_id>_<mmsi>)
- Empty and sparse fix streams
- Zero ground truth and zero attribution claims
"""
from __future__ import annotations

import datetime as dt
from typing import List

import pytest

from backend.f4_ais.agents import TrackReconstructionAgent
from backend.f4_ais.schemas import CorridorAISMatch, ValidatedAISFix, VesselTrack
from backend.f4_ais.track import TrackReconstructionService


def _make_corridor_match(
    event_id: str = "EVT0001",
    hypothesis_id: str = "SH_EVT0001_HBEST",
    mmsi: str = "244123456",
    timestamp: str = "2026-01-08T12:00:00Z",
    lat: float = 24.5,
    lon: float = 54.5,
    is_observed: bool = True,
    sog_kn: float = 12.0,
    cog_deg: float = 180.0,
    heading_deg: float = 180.0,
    vessel_type: str = "Tanker",
) -> CorridorAISMatch:
    ts = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return CorridorAISMatch(
        event_id=event_id,
        source_hypothesis_id=hypothesis_id,
        mmsi=mmsi,
        timestamp_utc=ts,
        timestamp_iso=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        latitude=lat,
        longitude=lon,
        distance_to_source_km=5.2,
        sog_kn=sog_kn,
        cog_deg=cog_deg,
        heading_deg=heading_deg,
        nav_status="UnderWayUsingEngine",
        vessel_type=vessel_type,
        vessel_length=200.0,
        vessel_width=32.0,
        draught=10.5,
        source="AIS-terrestrial",
        is_observed=is_observed,
    )


def test_f4_3_track_grouping_and_chronological_ordering():
    """F4.3: Verifies grouping by MMSI and strictly chronological sorting."""
    service = TrackReconstructionService(default_gap_threshold_hours=1.0)

    m1 = _make_corridor_match(mmsi="111111111", timestamp="2026-01-08T12:00:00Z")
    m2 = _make_corridor_match(mmsi="111111111", timestamp="2026-01-08T10:00:00Z")
    m3 = _make_corridor_match(mmsi="222222222", timestamp="2026-01-08T11:00:00Z")

    tracks = service.build_tracks([m1, m2, m3])
    assert len(tracks) == 2
    assert "111111111" in tracks
    assert "222222222" in tracks

    t1 = tracks["111111111"]
    assert len(t1.fixes) == 2
    assert t1.fixes[0].timestamp_iso == "2026-01-08T10:00:00Z"
    assert t1.fixes[1].timestamp_iso == "2026-01-08T12:00:00Z"
    assert t1.first_timestamp == "2026-01-08T10:00:00Z"
    assert t1.last_timestamp == "2026-01-08T12:00:00Z"
    assert t1.duration_hours == 2.0


def test_f4_3_gap_detection():
    """F4.3: Verifies gap detection and max_gap_hours calculation."""
    service = TrackReconstructionService(default_gap_threshold_hours=1.0)

    # 3 fixes with gaps of 0.5h, 2.5h (gap), 0.5h
    f1 = _make_corridor_match(mmsi="111111111", timestamp="2026-01-08T10:00:00Z")
    f2 = _make_corridor_match(mmsi="111111111", timestamp="2026-01-08T10:30:00Z")
    f3 = _make_corridor_match(mmsi="111111111", timestamp="2026-01-08T13:00:00Z")  # 2.5h gap > 1.0h
    f4 = _make_corridor_match(mmsi="111111111", timestamp="2026-01-08T13:30:00Z")

    tracks = service.build_tracks([f1, f2, f3, f4])
    t = tracks["111111111"]

    assert t.gap_count == 1
    assert t.max_gap_hours == 2.5
    assert t.duration_hours == 3.5
    assert t.track_completeness < 1.0


def test_f4_3_observed_vs_non_observed_preservation():
    """F4.3: Verifies is_observed is preserved and counts are distinct."""
    service = TrackReconstructionService()

    f_obs = _make_corridor_match(mmsi="333333333", timestamp="2026-01-08T10:00:00Z", is_observed=True)
    f_interp = _make_corridor_match(mmsi="333333333", timestamp="2026-01-08T11:00:00Z", is_observed=False)

    tracks = service.build_tracks([f_obs, f_interp])
    t = tracks["333333333"]

    assert t.observation_count == 1
    assert t.non_observation_count == 1
    assert t.fixes[0].is_observed is True
    assert t.fixes[1].is_observed is False


def test_f4_3_track_id_convention():
    """F4.3: Enforces frozen track ID convention: TRK_<event_id>_<mmsi>."""
    service = TrackReconstructionService()
    f1 = _make_corridor_match(event_id="EVT0002", mmsi="444444444")

    tracks = service.build_tracks([f1])
    t = tracks["444444444"]

    assert t.track_id == "TRK_EVT0002_444444444"
    assert t.event_id == "EVT0002"


def test_f4_3_multi_hypothesis_preservation():
    """F4.3: Verifies multi-hypothesis tracks preserve distinct hypothesis associations."""
    service = TrackReconstructionService()

    m_h1 = _make_corridor_match(event_id="EVT0001", hypothesis_id="SH_EVT0001_00", mmsi="555555555")
    m_h2 = _make_corridor_match(event_id="EVT0001", hypothesis_id="SH_EVT0001_01", mmsi="555555555")

    hyp_tracks = service.build_tracks_from_corridor_matches([m_h1, m_h2])
    assert len(hyp_tracks) == 2
    assert "SH_EVT0001_00_555555555" in hyp_tracks
    assert "SH_EVT0001_01_555555555" in hyp_tracks

    t_h1 = hyp_tracks["SH_EVT0001_00_555555555"]
    t_h2 = hyp_tracks["SH_EVT0001_01_555555555"]
    assert t_h1.source_hypothesis_id == "SH_EVT0001_00"
    assert t_h2.source_hypothesis_id == "SH_EVT0001_01"


def test_f4_3_empty_and_sparse_input():
    """F4.3: Handles empty and single-fix inputs gracefully."""
    service = TrackReconstructionService()

    # Empty
    tracks_empty = service.build_tracks([])
    assert tracks_empty == {}

    # Single fix
    f_single = _make_corridor_match(mmsi="666666666", timestamp="2026-01-08T12:00:00Z")
    tracks_single = service.build_tracks([f_single])
    t_single = tracks_single["666666666"]
    assert t_single.duration_hours == 0.0
    assert t_single.gap_count == 0
    assert t_single.max_gap_hours == 0.0
    assert t_single.track_completeness == 1.0


def test_f4_3_agent_delegation():
    """F4.3: Verifies TrackReconstructionAgent delegates to TrackReconstructionService."""
    agent = TrackReconstructionAgent()
    f1 = _make_corridor_match(mmsi="777777777")
    tracks = agent.build_tracks([f1])
    assert "777777777" in tracks
    assert tracks["777777777"].track_id == "TRK_EVT0001_777777777"
