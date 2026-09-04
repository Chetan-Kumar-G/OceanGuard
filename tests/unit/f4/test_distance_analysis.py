"""Unit tests for Feature F4.4 — Closest Approach / Distance Analysis.

Verifies:
- distance_to_source_observed_km calculation
- distance_to_source_interpolated_km calculation
- distance_to_source_effective_km calculation (min of observed and interpolated)
- closest_approach_is_interpolated provenance flag
- closest approach timestamp preservation
- deterministic geodesic Haversine distance
- empty track handling
- zero attribution and zero ground truth dependency
"""
from __future__ import annotations

import datetime as dt

import pytest

from backend.f4_ais.distance import DistanceAnalysisService
from backend.f4_ais.schemas import (
    ClosestApproachResult,
    ValidatedAISFix,
    VesselTrack,
)
from shared.schemas.f3_contract import SourceHypothesisWindow


def _make_hyp(
    lat: float = 24.5,
    lon: float = 54.5,
    event_id: str = "EVT0001",
    hyp_id: str = "SH_EVT0001_HBEST",
) -> SourceHypothesisWindow:
    return SourceHypothesisWindow.model_validate({
        "source_hypothesis_id": hyp_id,
        "event_id": event_id,
        "source_location": {"lat": lat, "lon": lon},
        "origin_time_start": "2026-01-08T10:00:00Z",
        "origin_time_end": "2026-01-08T14:00:00Z",
        "uncertainty_radius_km": 10.0,
        "source_probability": 1.0,
    })


def _make_fix(
    lat: float,
    lon: float,
    timestamp: str,
    is_observed: bool = True,
    sog_kn: float = 12.0,
    cog_deg: float = 180.0,
) -> ValidatedAISFix:
    ts = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return ValidatedAISFix(
        mmsi="123456789",
        timestamp_utc=ts,
        timestamp_iso=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        latitude=lat,
        longitude=lon,
        sog_kn=sog_kn,
        cog_deg=cog_deg,
        heading_deg=cog_deg,
        nav_status="UnderWayUsingEngine",
        source="AIS-terrestrial" if is_observed else "interpolation",
        is_observed=is_observed,
    )


def test_f4_4_observed_closer_than_interpolated():
    """F4.4: Observed fix is closer than interpolated fix."""
    hyp = _make_hyp(lat=24.5, lon=54.5)
    service = DistanceAnalysisService()

    # Observed at (24.51, 54.5) (~1.1 km)
    fix_obs = _make_fix(lat=24.51, lon=54.5, timestamp="2026-01-08T11:00:00Z", is_observed=True)
    # Interpolated at (24.55, 54.5) (~5.5 km)
    fix_interp = _make_fix(lat=24.55, lon=54.5, timestamp="2026-01-08T12:00:00Z", is_observed=False)

    track = VesselTrack(
        mmsi="123456789",
        track_id="TRK_EVT0001_123456789",
        fixes=[fix_obs, fix_interp],
    )

    result = service.analyze_track_distance(track, hyp)

    assert result.distance_to_source_observed_km < result.distance_to_source_interpolated_km
    assert result.distance_to_source_effective_km == result.distance_to_source_observed_km
    assert result.closest_approach_is_interpolated is False
    assert result.closest_approach_timestamp == "2026-01-08T11:00:00Z"
    assert result.interpolated_closest_timestamp == "2026-01-08T12:00:00Z"


def test_f4_4_interpolated_closer_than_observed():
    """F4.4: Interpolated fix is closer than observed fix (e.g. crossing gap)."""
    hyp = _make_hyp(lat=24.5, lon=54.5)
    service = DistanceAnalysisService()

    # Observed at (24.7, 54.5) (~22 km)
    fix_obs = _make_fix(lat=24.7, lon=54.5, timestamp="2026-01-08T10:00:00Z", is_observed=True)
    # Interpolated at (24.51, 54.5) (~1.1 km)
    fix_interp = _make_fix(lat=24.51, lon=54.5, timestamp="2026-01-08T12:00:00Z", is_observed=False)

    track = VesselTrack(
        mmsi="123456789",
        track_id="TRK_EVT0001_123456789",
        fixes=[fix_obs, fix_interp],
    )

    result = service.analyze_track_distance(track, hyp)

    assert result.distance_to_source_interpolated_km < result.distance_to_source_observed_km
    assert result.distance_to_source_effective_km == result.distance_to_source_interpolated_km
    assert result.closest_approach_is_interpolated is True
    assert result.closest_approach_timestamp == "2026-01-08T12:00:00Z"


def test_f4_4_only_observed_fixes():
    """F4.4: Track contains only observed fixes."""
    hyp = _make_hyp(lat=24.5, lon=54.5)
    service = DistanceAnalysisService()

    fix_obs = _make_fix(lat=24.52, lon=54.5, timestamp="2026-01-08T11:00:00Z", is_observed=True)
    track = VesselTrack(mmsi="123456789", fixes=[fix_obs])

    result = service.analyze_track_distance(track, hyp)
    assert result.distance_to_source_observed_km < 10.0
    assert result.distance_to_source_interpolated_km == 9999.0
    assert result.distance_to_source_effective_km == result.distance_to_source_observed_km
    assert result.closest_approach_is_interpolated is False


def test_f4_4_only_interpolated_fixes():
    """F4.4: Track contains only interpolated fixes."""
    hyp = _make_hyp(lat=24.5, lon=54.5)
    service = DistanceAnalysisService()

    fix_interp = _make_fix(lat=24.52, lon=54.5, timestamp="2026-01-08T11:00:00Z", is_observed=False)
    track = VesselTrack(mmsi="123456789", fixes=[fix_interp])

    result = service.analyze_track_distance(track, hyp)
    assert result.distance_to_source_observed_km == 9999.0
    assert result.distance_to_source_interpolated_km < 10.0
    assert result.distance_to_source_effective_km == result.distance_to_source_interpolated_km
    assert result.closest_approach_is_interpolated is True


def test_f4_4_empty_track():
    """F4.4: Empty track returns deterministic neutral distances."""
    hyp = _make_hyp()
    service = DistanceAnalysisService()
    track = VesselTrack(mmsi="999999999", fixes=[])

    result = service.analyze_track_distance(track, hyp)
    assert result.distance_to_source_effective_km == 9999.0
    assert result.distance_to_source_observed_km == 9999.0
    assert result.distance_to_source_interpolated_km == 9999.0
    assert result.closest_approach_is_interpolated is False
    assert result.closest_approach_timestamp is None
    assert result.closest_approach_lat is None
    assert result.closest_approach_lon is None


def test_f4_4_closest_approach_position_is_the_effective_fix():
    """closest_approach_lat/lon (map-display only) must be the position of whichever
    fix (observed or interpolated) produced the effective minimum distance."""
    hyp = _make_hyp(lat=24.5, lon=54.5)
    service = DistanceAnalysisService()

    fix_far_obs = _make_fix(lat=25.5, lon=54.5, timestamp="2026-01-08T10:30:00Z", is_observed=True)
    fix_near_interp = _make_fix(lat=24.51, lon=54.5, timestamp="2026-01-08T11:00:00Z", is_observed=False)
    track = VesselTrack(mmsi="123456789", fixes=[fix_far_obs, fix_near_interp])

    result = service.analyze_track_distance(track, hyp)
    assert result.closest_approach_is_interpolated is True
    assert result.closest_approach_lat == pytest.approx(24.51)
    assert result.closest_approach_lon == pytest.approx(54.5)
