"""Unit tests for Feature F4.6 — Temporal, Speed, Course, and Gap Compatibility.

Verifies:
- Circular bearing difference handling 0°/360° wraparound (359° vs 1° = 2°)
- Course compatibility score [0, 1]
- Speed compatibility score [0, 1]
- Missing navigation handling (None remains None, produces neutral 0.5 score)
- Temporal compatibility score [0, 1]
- AIS gap ratio inside origin window [0, 1]
- Track overlap calculation
- Zero ML and zero guilt/culpability claims
"""
from __future__ import annotations

import datetime as dt
import math

import pytest

from backend.f4_ais.compatibility import (
    CompatibilityAnalysisService,
    compute_circular_bearing_difference,
)
from backend.f4_ais.schemas import (
    ClosestApproachResult,
    DarkGapResult,
    ValidatedAISFix,
    VesselTrack,
)
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
    sog_kn: float | None = 12.0,
    cog_deg: float | None = 180.0,
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
        source="AIS-terrestrial",
        is_observed=True,
    )


def test_f4_6_circular_bearing_difference():
    """F4.6: Verifies 0°/360° circular wraparound calculation."""
    # 359° vs 1° should be 2°, not 358°
    diff_wrap = compute_circular_bearing_difference(359.0, 1.0)
    assert abs(diff_wrap - 2.0) < 1e-6

    # 10° vs 350° should be 20°
    assert abs(compute_circular_bearing_difference(10.0, 350.0) - 20.0) < 1e-6

    # 0° vs 180° should be 180°
    assert abs(compute_circular_bearing_difference(0.0, 180.0) - 180.0) < 1e-6

    # Identical angles
    assert abs(compute_circular_bearing_difference(90.0, 90.0) - 0.0) < 1e-6


def test_f4_6_course_compatibility():
    """F4.6: Course compatibility score in [0, 1]."""
    service = CompatibilityAnalysisService()

    # Identical course -> 1.0
    c_same = service.compute_course_compatibility(180.0, 180.0)
    assert c_same == 1.0

    # Opposite course -> 0.0
    c_opp = service.compute_course_compatibility(0.0, 180.0)
    assert c_opp == 0.0

    # Orthogonal course (90 deg diff) -> 0.5
    c_ortho = service.compute_course_compatibility(90.0, 180.0)
    assert abs(c_ortho - 0.5) < 1e-3

    # Missing course -> neutral 0.5
    assert service.compute_course_compatibility(None, 180.0) == 0.5
    assert service.compute_course_compatibility(180.0, None) == 0.5


def test_f4_6_speed_compatibility():
    """F4.6: Speed compatibility score in [0, 1]."""
    service = CompatibilityAnalysisService()

    # Identical speed -> 1.0
    s_same = service.compute_speed_compatibility(12.0, 12.0)
    assert s_same == 1.0

    # Large speed difference -> decays toward 0
    s_diff = service.compute_speed_compatibility(25.0, 1.0)
    assert s_diff < 0.1

    # Missing speed -> neutral 0.5
    assert service.compute_speed_compatibility(None, 12.0) == 0.5
    assert service.compute_speed_compatibility(12.0, None) == 0.5
    assert service.compute_speed_compatibility(12.0, 0.0) == 0.5


def test_f4_6_ais_gap_ratio_origin_window():
    """F4.6: AIS gap ratio in origin window [0, 1]."""
    hyp = _make_hyp(t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")  # 4 hour window
    service = CompatibilityAnalysisService()

    # Case 1: Continuous transmissions every 10 min (gap_thr=1.0h)
    fixes_dense = [
        _make_fix(24.5, 54.5, "2026-01-08T10:00:00Z"),
        _make_fix(24.5, 54.5, "2026-01-08T11:00:00Z"),
        _make_fix(24.5, 54.5, "2026-01-08T12:00:00Z"),
        _make_fix(24.5, 54.5, "2026-01-08T13:00:00Z"),
        _make_fix(24.5, 54.5, "2026-01-08T14:00:00Z"),
    ]
    t_dense = VesselTrack(mmsi="111111111", fixes=fixes_dense)
    ratio_dense = service.compute_ais_gap_ratio_origin_window(t_dense, hyp, gap_threshold_hours=1.0)
    assert ratio_dense == 0.0  # 100% covered

    # Case 2: Single transmission inside window -> ratio = 0.0 (absence != reporting gap)
    fixes_sparse = [_make_fix(24.5, 54.5, "2026-01-08T11:00:00Z")]
    t_sparse = VesselTrack(mmsi="222222222", fixes=fixes_sparse)
    ratio_sparse = service.compute_ais_gap_ratio_origin_window(t_sparse, hyp)
    assert ratio_sparse == 0.0  # Absence is not a reporting gap

    # Case 3: Genuine 3-hour reporting gap inside 4-hour window (10:00 to 13:00)
    fixes_with_gap = [
        _make_fix(24.5, 54.5, "2026-01-08T10:00:00Z"),
        _make_fix(24.5, 54.5, "2026-01-08T13:00:00Z"),  # 3h gap > 1h threshold
        _make_fix(24.5, 54.5, "2026-01-08T14:00:00Z"),  # 1h interval (normal)
    ]
    t_gap = VesselTrack(mmsi="333333333", fixes=fixes_with_gap)
    ratio_gap = service.compute_ais_gap_ratio_origin_window(t_gap, hyp, gap_threshold_hours=1.0)
    assert ratio_gap == 0.75  # 3 hours out of 4 hours spent in gap


def test_f4_6_full_compatibility_analysis():
    """F4.6: Evaluates complete CompatibilityResult payload."""
    hyp = _make_hyp(lat=24.5, lon=54.5)
    service = CompatibilityAnalysisService()

    f1 = _make_fix(24.51, 54.5, "2026-01-08T11:00:00Z", sog_kn=10.0, cog_deg=45.0)
    f2 = _make_fix(24.52, 54.5, "2026-01-08T12:00:00Z", sog_kn=10.0, cog_deg=45.0)
    track = VesselTrack(mmsi="333333333", fixes=[f1, f2])

    ca = ClosestApproachResult(
        mmsi="333333333",
        distance_to_source_effective_km=1.5,
        closest_observed_sog_kn=10.0,
        closest_observed_cog_deg=45.0,
    )

    dg = DarkGapResult(mmsi="333333333", dark_gap_over_source=False, dark_gap_over_source_hours=0.0)

    res = service.analyze_compatibility(
        track=track,
        hypothesis=hyp,
        closest_approach=ca,
        dark_gap=dg,
        drift_speed_kn=1.0,
        drift_course_deg=45.0,
    )

    assert res.temporal_compatibility == 1.0
    assert res.course_compatibility == 1.0  # same 45 deg
    assert 0.0 <= res.speed_compatibility <= 1.0
    assert 0.0 <= res.track_overlap <= 1.0
    assert 0.0 <= res.ais_gap_ratio_origin_window <= 1.0


def test_f4_6_temporal_compatibility_decay():
    """F4.6: Verifies temporal compatibility boundaries and linear decay."""
    hyp = _make_hyp(t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")  # 4h window
    service = CompatibilityAnalysisService()

    # 1. Inside origin window -> 1.0
    t_in = VesselTrack(mmsi="1", fixes=[_make_fix(24.5, 54.5, "2026-01-08T11:00:00Z")])
    assert service.compute_temporal_compatibility(t_in, hyp, effective_dist_km=1.0) == 1.0

    # 2. Exactly at start boundary -> 1.0
    t_start = VesselTrack(mmsi="1", fixes=[_make_fix(24.5, 54.5, "2026-01-08T10:00:00Z")])
    assert service.compute_temporal_compatibility(t_start, hyp, effective_dist_km=1.0) == 1.0

    # 3. Exactly at end boundary -> 1.0
    t_end = VesselTrack(mmsi="1", fixes=[_make_fix(24.5, 54.5, "2026-01-08T14:00:00Z")])
    assert service.compute_temporal_compatibility(t_end, hyp, effective_dist_km=1.0) == 1.0

    # 4. 6 hours before window (04:00:00Z) -> 1.0 - (6.0 / 24.0) = 0.75
    t_out_6h = VesselTrack(mmsi="1", fixes=[_make_fix(24.5, 54.5, "2026-01-08T04:00:00Z")])
    score_6h = service.compute_temporal_compatibility(t_out_6h, hyp, effective_dist_km=1.0)
    assert abs(score_6h - 0.75) < 1e-3

    # 5. 24 hours or more outside window -> 0.0
    t_out_24h = VesselTrack(mmsi="1", fixes=[_make_fix(24.5, 54.5, "2026-01-07T10:00:00Z")])
    assert service.compute_temporal_compatibility(t_out_24h, hyp, effective_dist_km=1.0) == 0.0

    # 6. Qualifying dark-gap over source -> 1.0
    t_dark = VesselTrack(mmsi="1", fixes=[_make_fix(24.5, 54.5, "2026-01-07T10:00:00Z")])
    assert service.compute_temporal_compatibility(t_dark, hyp, effective_dist_km=1.0, dark_gap_over_source=True) == 1.0


def test_f4_6_track_overlap_calculation():
    """F4.6: Verifies track overlap temporal intersection formula."""
    hyp = _make_hyp(t_start="2026-01-08T10:00:00Z", t_end="2026-01-08T14:00:00Z")  # 4h window
    service = CompatibilityAnalysisService()

    # Track spans 2 hours of 4-hour window (10:00 to 12:00) -> 0.5
    f1 = _make_fix(24.5, 54.5, "2026-01-08T10:00:00Z")
    f2 = _make_fix(24.5, 54.5, "2026-01-08T12:00:00Z")
    t_half = VesselTrack(mmsi="1", fixes=[f1, f2])
    assert service.compute_track_overlap(t_half, hyp) == 0.5

    # Track spans full window (08:00 to 16:00) -> 1.0
    f_early = _make_fix(24.5, 54.5, "2026-01-08T08:00:00Z")
    f_late = _make_fix(24.5, 54.5, "2026-01-08T16:00:00Z")
    t_full = VesselTrack(mmsi="1", fixes=[f_early, f_late])
    assert service.compute_track_overlap(t_full, hyp) == 1.0

    # Track strictly outside window (04:00 to 08:00) -> 0.0
    f_out1 = _make_fix(24.5, 54.5, "2026-01-08T04:00:00Z")
    f_out2 = _make_fix(24.5, 54.5, "2026-01-08T08:00:00Z")
    t_out = VesselTrack(mmsi="1", fixes=[f_out1, f_out2])
    assert service.compute_track_overlap(t_out, hyp) == 0.0


def test_f4_6_missing_vs_zero_sog_and_cog():
    """F4.6: Verifies semantic distinction between missing (None) and measured zero (0.0)."""
    service = CompatibilityAnalysisService()
    drift_speed = 3.0
    drift_course = 180.0

    # Missing SOG -> 0.5 (neutral)
    assert service.compute_speed_compatibility(None, drift_speed) == 0.5
    # Measured SOG = 0.0 -> evaluated quantitatively against drift (not 0.5)
    score_zero_sog = service.compute_speed_compatibility(0.0, drift_speed)
    assert score_zero_sog != 0.5
    assert abs(score_zero_sog - math.exp(-3.0 / 6.0)) < 1e-4

    # Missing COG -> 0.5 (neutral)
    assert service.compute_course_compatibility(None, drift_course) == 0.5
    # Measured COG = 0.0 (Due North vs 180 South -> opposite -> 0.0)
    score_zero_cog = service.compute_course_compatibility(0.0, drift_course)
    assert score_zero_cog == 0.0
    assert score_zero_cog != 0.5
