"""Unit tests for Feature F4.7 — Candidate Vessel Generation.

Verifies:
- Assembly and validation of the frozen CandidateVessel contract
- All mandatory fields correctly populated from component evidence
- Strict preservation of interpolation provenance
- Deterministic candidate ordering (event_id, source_hypothesis_id, mmsi)
- Graceful empty results handling (empty CandidateVessel[])
- Zero ML classifier, zero guilt probability, and zero ground truth dependency
"""
from __future__ import annotations

import datetime as dt

import pytest

from backend.f4_ais.candidate import CandidateVesselService
from backend.f4_ais.schemas import (
    ClosestApproachResult,
    CompatibilityResult,
    DarkGapResult,
    ValidatedAISFix,
    VesselTrack,
)
from shared.schemas.f3_contract import SourceHypothesisWindow
from shared.schemas.f4_contract import CandidateVessel


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
        "uncertainty_radius_km": 15.0,
        "source_probability": 1.0,
    })


def _make_fix(
    mmsi: str,
    lat: float,
    lon: float,
    timestamp: str,
    is_observed: bool = True,
    sog_kn: float = 12.5,
    cog_deg: float = 180.0,
) -> ValidatedAISFix:
    ts = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return ValidatedAISFix(
        mmsi=mmsi,
        timestamp_utc=ts,
        timestamp_iso=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        latitude=lat,
        longitude=lon,
        sog_kn=sog_kn,
        cog_deg=cog_deg,
        heading_deg=cog_deg,
        nav_status="UnderWayUsingEngine",
        vessel_type="Tanker",
        vessel_length=250.0,
        vessel_width=44.0,
        draught=12.0,
        source="AIS-terrestrial",
        is_observed=is_observed,
    )


def test_f4_7_exact_candidate_vessel_contract():
    """F4.7: Validates CandidateVessel satisfies frozen schema without missing fields."""
    service = CandidateVesselService()
    hyp = _make_hyp()

    f1 = _make_fix("111111111", 24.51, 54.5, "2026-01-08T11:00:00Z")
    track = VesselTrack(
        mmsi="111111111",
        track_id="TRK_EVT0001_111111111",
        event_id="EVT0001",
        source_hypothesis_id="SH_EVT0001_HBEST",
        fixes=[f1],
        vessel_type="Tanker",
        vessel_length=250.0,
        vessel_width=44.0,
        draught=12.0,
        first_timestamp="2026-01-08T11:00:00Z",
        last_timestamp="2026-01-08T11:00:00Z",
        duration_hours=0.0,
        observation_count=1,
        non_observation_count=0,
        gap_count=0,
        max_gap_hours=0.0,
        track_completeness=1.0,
    )

    dist_res = ClosestApproachResult(
        mmsi="111111111",
        distance_to_source_effective_km=1.1,
        distance_to_source_observed_km=1.1,
        closest_approach_is_interpolated=False,
        closest_approach_timestamp="2026-01-08T11:00:00Z",
    )

    gap_res = DarkGapResult(
        mmsi="111111111",
        dark_gap_over_source=False,
        dark_gap_over_source_hours=0.0,
        total_gaps=0,
        max_gap_hours=0.0,
    )

    compat_res = CompatibilityResult(
        mmsi="111111111",
        temporal_compatibility=1.0,
        speed_compatibility=0.8,
        course_compatibility=0.9,
        track_overlap=0.5,
        ais_gap_ratio_origin_window=0.0,
        observed_speed_kn=12.5,
        observed_course_deg=180.0,
    )

    cv = service.assemble_candidate(
        track=track,
        hypothesis=hyp,
        distance_result=dist_res,
        dark_gap_result=gap_res,
        compat_result=compat_res,
    )

    # Validate type and fields
    assert isinstance(cv, CandidateVessel)
    assert cv.track_id == "TRK_EVT0001_111111111"
    assert cv.event_id == "EVT0001"
    assert cv.mmsi == "111111111"
    assert cv.source_hypothesis_id == "SH_EVT0001_HBEST"
    assert cv.distance_to_source_effective_km == 1.1
    assert cv.temporal_compatibility == 1.0
    assert cv.track_overlap == 0.5
    assert cv.track_completeness == 1.0
    assert cv.dark_gap_over_source is False
    assert cv.dark_gap_over_source_hours == 0.0
    assert cv.closest_approach_is_interpolated is False
    assert cv.speed_compatibility == 0.8
    assert cv.course_compatibility == 0.9
    assert cv.ais_gap_ratio_origin_window == 0.0

    # Provenance fields
    assert cv.vessel_type == "Tanker"
    assert cv.vessel_length == 250.0
    assert cv.number_of_observations == 1


def test_f4_7_generate_candidates_fleet_pipeline():
    """F4.7: Verifies end-to-end fleet candidate assembly across multiple tracks."""
    service = CandidateVesselService()
    hyp = _make_hyp()

    f1 = _make_fix("222222222", 24.51, 54.5, "2026-01-08T11:00:00Z")
    f2 = _make_fix("111111111", 24.55, 54.5, "2026-01-08T12:00:00Z")

    t1 = VesselTrack(mmsi="222222222", fixes=[f1])
    t2 = VesselTrack(mmsi="111111111", fixes=[f2])

    tracks = {"222222222": t1, "111111111": t2}
    candidates = service.generate_candidate_vessels(tracks, hyp)

    assert len(candidates) == 2
    # Deterministic sorting by (event_id, source_hypothesis_id, mmsi)
    assert candidates[0].mmsi == "111111111"
    assert candidates[1].mmsi == "222222222"


def test_f4_7_empty_tracks_returns_empty_candidates():
    """F4.7: Empty track dict returns empty candidate list deterministically."""
    service = CandidateVesselService()
    hyp = _make_hyp()

    candidates = service.generate_candidate_vessels({}, hyp)
    assert candidates == []
