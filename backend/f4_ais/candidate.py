"""Feature F4.7 — Candidate Vessel Generation Service.

Assembles the frozen F4 -> F5 CandidateVessel contract from upstream evidence:
- F4.3: VesselTrack (chronology, completeness, gaps)
- F4.4: ClosestApproachResult (observed, interpolated, effective distance)
- F4.5: DarkGapResult (dark gap over source, duration)
- F4.6: CompatibilityResult (temporal, speed, course, gap ratio)

CRITICAL SAFETY PRINCIPLES:
- Candidate generation is strictly deterministic and auditable.
- NO ML classifier or black-box ranking model is used.
- NO guilt, culpability, or responsibility fields are generated.
- Strict isolation of ground truth (never reads evaluation labels or ground truth files).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from shared.schemas.f3_contract import SourceHypothesisWindow
from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.compatibility import CompatibilityAnalysisService
from backend.f4_ais.distance import DistanceAnalysisService
from backend.f4_ais.gap import DarkGapAnalysisService
from backend.f4_ais.schemas import (
    ClosestApproachResult,
    CompatibilityResult,
    DarkGapResult,
    VesselTrack,
)


class CandidateVesselService:
    """Deterministic domain service for assembling CandidateVessel contracts."""

    def __init__(
        self,
        distance_service: Optional[DistanceAnalysisService] = None,
        gap_service: Optional[DarkGapAnalysisService] = None,
        compat_service: Optional[CompatibilityAnalysisService] = None,
    ) -> None:
        self.distance_service = distance_service or DistanceAnalysisService()
        self.gap_service = gap_service or DarkGapAnalysisService()
        self.compat_service = compat_service or CompatibilityAnalysisService()

    @staticmethod
    def format_track_id(event_id: str, mmsi: str) -> str:
        """Enforces the frozen Track ID convention: TRK_<event_id>_<mmsi>."""
        return f"TRK_{event_id}_{mmsi}"

    def assemble_candidate(
        self,
        track: VesselTrack,
        hypothesis: SourceHypothesisWindow,
        distance_result: ClosestApproachResult,
        dark_gap_result: DarkGapResult,
        compat_result: CompatibilityResult,
    ) -> CandidateVessel:
        """Assembles and validates a single CandidateVessel contract from component evidence."""
        event_id = hypothesis.event_id
        hyp_id = hypothesis.source_hypothesis_id
        mmsi = track.mmsi
        track_id = self.format_track_id(event_id, mmsi)

        return CandidateVessel(
            track_id=track_id,
            event_id=event_id,
            mmsi=str(mmsi),
            source_hypothesis_id=hyp_id,
            distance_to_source_effective_km=distance_result.distance_to_source_effective_km,
            temporal_compatibility=compat_result.temporal_compatibility,
            track_overlap=compat_result.track_overlap,
            track_completeness=track.track_completeness,
            dark_gap_over_source=dark_gap_result.dark_gap_over_source,
            dark_gap_over_source_hours=dark_gap_result.dark_gap_over_source_hours,
            closest_approach_is_interpolated=distance_result.closest_approach_is_interpolated,
            speed_compatibility=compat_result.speed_compatibility,
            course_compatibility=compat_result.course_compatibility,
            ais_gap_ratio_origin_window=compat_result.ais_gap_ratio_origin_window,
            # Provenance and audit fields
            vessel_type=track.vessel_type,
            vessel_length=track.vessel_length,
            vessel_width=track.vessel_width,
            draught=track.draught,
            first_timestamp=track.first_timestamp,
            last_timestamp=track.last_timestamp,
            track_duration_h=track.duration_hours,
            number_of_observations=track.observation_count,
            gap_count=track.gap_count,
            max_gap_hours=track.max_gap_hours,
            distance_to_source_km=distance_result.distance_to_source_observed_km,
            distance_to_source_interpolated_km=distance_result.distance_to_source_interpolated_km,
            closest_approach_timestamp=distance_result.closest_approach_timestamp,
            interpolated_closest_timestamp=distance_result.interpolated_closest_timestamp,
            observed_speed_kn=compat_result.observed_speed_kn,
            observed_course_deg=compat_result.observed_course_deg,
            slick_drift_speed_kn=compat_result.slick_drift_speed_kn,
            slick_drift_course_deg=compat_result.slick_drift_course_deg,
            closest_approach_lat=distance_result.closest_approach_lat,
            closest_approach_lon=distance_result.closest_approach_lon,
        )

    def generate_candidate_vessels(
        self,
        tracks: Dict[str, VesselTrack],
        hypothesis: SourceHypothesisWindow,
        drift_speed_kn: Optional[float] = None,
        drift_course_deg: Optional[float] = None,
        gap_threshold_hours: float = 1.0,
    ) -> List[CandidateVessel]:
        """Generates CandidateVessel records for all provided tracks against a source hypothesis.

        Results are deterministically sorted by (event_id, source_hypothesis_id, mmsi).
        """
        if not tracks:
            return []

        candidates: List[CandidateVessel] = []
        for key in sorted(tracks.keys()):
            trk = tracks[key]
            dist_res = self.distance_service.analyze_track_distance(trk, hypothesis)
            gap_res = self.gap_service.analyze_dark_gap(trk, hypothesis, gap_threshold_hours=gap_threshold_hours)
            compat_res = self.compat_service.analyze_compatibility(
                track=trk,
                hypothesis=hypothesis,
                closest_approach=dist_res,
                dark_gap=gap_res,
                drift_speed_kn=drift_speed_kn,
                drift_course_deg=drift_course_deg,
                gap_threshold_hours=gap_threshold_hours,
            )

            cv = self.assemble_candidate(
                track=trk,
                hypothesis=hypothesis,
                distance_result=dist_res,
                dark_gap_result=gap_res,
                compat_result=compat_res,
            )
            candidates.append(cv)

        # Deterministic sorting
        candidates.sort(key=lambda c: (c.event_id, c.source_hypothesis_id, c.mmsi))
        return candidates
