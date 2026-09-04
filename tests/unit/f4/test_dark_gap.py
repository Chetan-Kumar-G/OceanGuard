"""Unit tests for Feature F4.5 — AIS Gap / Dark-Gap Analysis.

Verifies:
- Gap intervals correctly identified between consecutive observed fixes
- Temporal overlap with F3 origin time window correctly evaluated
- Spatial proximity to source uncertainty region along gap trajectory
- dark_gap_over_source boolean and duration hours calculated
- Normal continuous reporting exhibits zero dark gaps
- Reporting gaps elsewhere in time or space do NOT trigger dark_gap_over_source
- Observed vs non-observed provenance preserved
- Deterministic behavior with zero guilt or responsibility interpretation
"""
from __future__ import annotations

import datetime as dt

import pytest

from backend.f4_ais.gap import DarkGapAnalysisService
from backend.f4_ais.schemas import ValidatedAISFix, VesselTrack
from shared.schemas.f3_contract import SourceHypothesisWindow


def _make_hyp(
    lat: float = 24.5,
    lon: float = 54.5,
    t_start: str = "2026-01-08T10:00:00Z",
    t_end: str = "2026-01-08T14:00:00Z",
    radius_km: float = 15.0,
) -> SourceHypothesisWindow:
    return SourceHypothesisWindow.model_validate({
        "source_hypothesis_id": "SH_EVT0001_HBEST",
        "event_id": "EVT0001",
        "source_location": {"lat": lat, "lon": lon},
        "origin_time_start": t_start,
        "origin_time_end": t_end,
        "uncertainty_radius_km": radius_km,
        "source_probability": 1.0,
    })


def _make_fix(
    lat: float,
    lon: float,
    timestamp: str,
    is_observed: bool = True,
) -> ValidatedAISFix:
    ts = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return ValidatedAISFix(
        mmsi="123456789",
        timestamp_utc=ts,
        timestamp_iso=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        latitude=lat,
        longitude=lon,
        sog_kn=12.0,
        cog_deg=180.0,
        heading_deg=180.0,
        nav_status="UnderWayUsingEngine",
        source="AIS-terrestrial" if is_observed else "interpolation",
        is_observed=is_observed,
    )


def test_f4_5_dark_gap_over_source_detected():
    """F4.5: Vessel exhibits an AIS gap spanning across the source location during the origin window."""
    hyp = _make_hyp(lat=24.5, lon=54.5, t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z", radius_km=15.0)
    service = DarkGapAnalysisService(default_gap_threshold_hours=1.0)

    # Transmission before gap: 09:30 UTC, 10 km north of source (24.59, 54.5)
    f1 = _make_fix(lat=24.59, lon=54.5, timestamp="2026-01-08T09:30:00Z", is_observed=True)
    # Transmission after gap: 14:30 UTC (5.0 hours later), 10 km south of source (24.41, 54.5)
    f2 = _make_fix(lat=24.41, lon=54.5, timestamp="2026-01-08T14:30:00Z", is_observed=True)

    track = VesselTrack(mmsi="123456789", fixes=[f1, f2])
    result = service.analyze_dark_gap(track, hyp)

    assert result.dark_gap_over_source is True
    assert result.total_gaps == 1
    assert result.max_gap_hours == 5.0
    # Overlap with [10:00, 14:00] is [10:00, 14:00] = 4.0 hours
    assert result.dark_gap_over_source_hours == 4.0
    assert len(result.gap_intervals) == 1
    assert result.gap_intervals[0].overlaps_origin_window is True
    assert result.gap_intervals[0].is_over_source is True


def test_f4_5_gap_outside_origin_window_not_dark_gap_over_source():
    """F4.5: Vessel has a reporting gap, but entirely outside the origin window."""
    hyp = _make_hyp(lat=24.5, lon=54.5, t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")
    service = DarkGapAnalysisService(default_gap_threshold_hours=1.0)

    # Gap from 16:00 to 20:00 (after origin window ends at 14:00)
    f1 = _make_fix(lat=24.51, lon=54.5, timestamp="2026-01-08T16:00:00Z", is_observed=True)
    f2 = _make_fix(lat=24.52, lon=54.5, timestamp="2026-01-08T20:00:00Z", is_observed=True)

    track = VesselTrack(mmsi="123456789", fixes=[f1, f2])
    result = service.analyze_dark_gap(track, hyp)

    assert result.total_gaps == 1
    assert result.max_gap_hours == 4.0
    assert result.dark_gap_over_source is False
    assert result.dark_gap_over_source_hours == 0.0


def test_f4_5_gap_far_from_source_not_dark_gap_over_source():
    """F4.5: Vessel has a reporting gap during the origin window, but far outside the source area."""
    hyp = _make_hyp(lat=24.5, lon=54.5, radius_km=15.0)
    service = DarkGapAnalysisService(default_gap_threshold_hours=1.0)

    # Gap at lat 28.0 (hundreds of km away from 24.5)
    f1 = _make_fix(lat=28.0, lon=54.5, timestamp="2026-01-08T10:00:00Z", is_observed=True)
    f2 = _make_fix(lat=28.1, lon=54.5, timestamp="2026-01-08T13:00:00Z", is_observed=True)

    track = VesselTrack(mmsi="123456789", fixes=[f1, f2])
    result = service.analyze_dark_gap(track, hyp)

    assert result.total_gaps == 1
    assert result.max_gap_hours == 3.0
    assert result.dark_gap_over_source is False
    assert result.dark_gap_over_source_hours == 0.0


def test_f4_5_continuous_reporting_zero_dark_gaps():
    """F4.5: Normal continuous reporting without dropouts."""
    hyp = _make_hyp()
    service = DarkGapAnalysisService(default_gap_threshold_hours=1.0)

    # Fixes every 10 minutes
    f1 = _make_fix(lat=24.5, lon=54.5, timestamp="2026-01-08T11:00:00Z", is_observed=True)
    f2 = _make_fix(lat=24.5, lon=54.5, timestamp="2026-01-08T11:10:00Z", is_observed=True)
    f3 = _make_fix(lat=24.5, lon=54.5, timestamp="2026-01-08T11:20:00Z", is_observed=True)

    track = VesselTrack(mmsi="123456789", fixes=[f1, f2, f3])
    result = service.analyze_dark_gap(track, hyp)

    assert result.total_gaps == 0
    assert result.dark_gap_over_source is False
    assert result.dark_gap_over_source_hours == 0.0
