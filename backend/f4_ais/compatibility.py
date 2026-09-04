"""Feature F4.6 — Temporal, Speed, Course, and AIS Gap Compatibility Service.

Calculates transparent, deterministic compatibility evidence features between
a vessel track and an F3 source hypothesis window.

CRITICAL SAFETY PRINCIPLE:
Compatibility scores are objective evidence metrics for downstream F5/F6 fusion.
They are NOT probabilities of guilt, legal liability, or attribution scores.
NO machine learning classifiers or black-box models are employed.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple, Union

from shared.schemas.f3_contract import SourceHypothesisWindow
from backend.f4_ais.corridor import haversine_distance_km
from backend.f4_ais.schemas import (
    ClosestApproachResult,
    CompatibilityResult,
    DarkGapResult,
    ValidatedAISFix,
    VesselTrack,
)
from backend.f4_ais.validation import parse_utc_timestamp


def compute_circular_bearing_difference(course1_deg: float, course2_deg: float) -> float:
    """Calculates shortest circular angular difference between two compass bearings in [0, 180] degrees.

    Correctly handles 0° / 360° wraparound:
        e.g., 359° vs 1° -> 2°, NOT 358°.
    """
    diff = abs(course1_deg - course2_deg) % 360.0
    return min(diff, 360.0 - diff)


class CompatibilityAnalysisService:
    """Deterministic domain service for calculating physical and temporal compatibility signals."""

    def analyze_compatibility(
        self,
        track: VesselTrack,
        hypothesis: SourceHypothesisWindow,
        closest_approach: Optional[ClosestApproachResult] = None,
        dark_gap: Optional[DarkGapResult] = None,
        drift_speed_kn: Optional[float] = None,
        drift_course_deg: Optional[float] = None,
        gap_threshold_hours: float = 1.0,
    ) -> CompatibilityResult:
        """Calculates all F4.6 compatibility signals for a vessel track against a source hypothesis."""
        event_id = hypothesis.event_id
        hyp_id = hypothesis.source_hypothesis_id
        mmsi = track.mmsi
        track_id = track.track_id or f"TRK_{event_id}_{mmsi}"

        if not track.fixes:
            return CompatibilityResult(
                mmsi=mmsi,
                track_id=track_id,
                event_id=event_id,
                source_hypothesis_id=hyp_id,
                temporal_compatibility=0.0,
                speed_compatibility=0.5,
                course_compatibility=0.5,
                track_overlap=0.0,
                ais_gap_ratio_origin_window=1.0,
                observed_speed_kn=None,
                observed_course_deg=None,
                slick_drift_speed_kn=drift_speed_kn,
                slick_drift_course_deg=drift_course_deg,
            )

        # Extract closest approach metrics
        eff_dist = closest_approach.distance_to_source_effective_km if closest_approach else 9999.0
        v_sog = closest_approach.closest_observed_sog_kn if closest_approach else None
        v_cog = closest_approach.closest_observed_cog_deg if closest_approach else None

        # Fallback to first observed fix if closest approach did not specify
        if v_sog is None:
            v_sog = next((f.sog_kn for f in track.fixes if f.is_observed and f.sog_kn is not None), None)
        if v_cog is None:
            v_cog = next((f.cog_deg for f in track.fixes if f.is_observed and f.cog_deg is not None), None)

        dark_over_source = dark_gap.dark_gap_over_source if dark_gap else False

        # 1. Temporal compatibility
        temporal_compat = self.compute_temporal_compatibility(
            track=track,
            hypothesis=hypothesis,
            effective_dist_km=eff_dist,
            dark_gap_over_source=dark_over_source,
        )

        # 2. Speed compatibility vs slick drift
        speed_compat = self.compute_speed_compatibility(
            vessel_sog_kn=v_sog,
            drift_speed_kn=drift_speed_kn,
        )

        # 3. Course compatibility vs slick drift
        course_compat = self.compute_course_compatibility(
            vessel_cog_deg=v_cog,
            drift_course_deg=drift_course_deg,
        )

        # 4. AIS gap ratio inside the origin window
        gap_ratio = self.compute_ais_gap_ratio_origin_window(
            track=track,
            hypothesis=hypothesis,
            gap_threshold_hours=gap_threshold_hours,
        )

        # 5. Track overlap in origin window
        overlap = self.compute_track_overlap(
            track=track,
            hypothesis=hypothesis,
        )

        return CompatibilityResult(
            mmsi=mmsi,
            track_id=track_id,
            event_id=event_id,
            source_hypothesis_id=hyp_id,
            temporal_compatibility=temporal_compat,
            speed_compatibility=speed_compat,
            course_compatibility=course_compat,
            track_overlap=overlap,
            ais_gap_ratio_origin_window=gap_ratio,
            observed_speed_kn=v_sog,
            observed_course_deg=v_cog,
            slick_drift_speed_kn=drift_speed_kn,
            slick_drift_course_deg=drift_course_deg,
        )

    def compute_temporal_compatibility(
        self,
        track: VesselTrack,
        hypothesis: SourceHypothesisWindow,
        effective_dist_km: float,
        dark_gap_over_source: bool = False,
        decay_window_hours: float = 24.0,
    ) -> float:
        """Evaluates whether vessel track timing aligns with the F3 origin window.

        MVP ASSUMPTION / FORMULATION:
        - 1.0 if vessel has an observation or dark-gap traversal inside [t_start, t_end].
        - Linear decay outside the window over decay_window_hours (default 24h) to 0.0.
        - Preserves explainable, deterministic bounds without magic exponential combinations.
        """
        if not track.fixes:
            return 0.0

        t_start = parse_utc_timestamp(hypothesis.origin_time_start)
        t_end = parse_utc_timestamp(hypothesis.origin_time_end)

        # Check if any fix falls inside origin window
        has_in_window = any(
            t_start <= (f.timestamp_utc if f.timestamp_utc.tzinfo else f.timestamp_utc.replace(tzinfo=timezone.utc)) <= t_end
            for f in track.fixes
        )
        if has_in_window or dark_gap_over_source:
            return 1.0

        # Linear decay outside window based on nearest temporal boundary
        t_first = track.fixes[0].timestamp_utc if track.fixes[0].timestamp_utc.tzinfo else track.fixes[0].timestamp_utc.replace(tzinfo=timezone.utc)
        t_last = track.fixes[-1].timestamp_utc if track.fixes[-1].timestamp_utc.tzinfo else track.fixes[-1].timestamp_utc.replace(tzinfo=timezone.utc)

        if t_last < t_start:
            dt_h = (t_start.timestamp() - t_last.timestamp()) / 3600.0
        elif t_first > t_end:
            dt_h = (t_first.timestamp() - t_end.timestamp()) / 3600.0
        else:
            dt_h = 0.0

        score = max(0.0, 1.0 - (dt_h / max(1.0, decay_window_hours)))
        return round(score, 4)

    def compute_speed_compatibility(
        self,
        vessel_sog_kn: Optional[float],
        drift_speed_kn: Optional[float],
    ) -> float:
        """Compares vessel speed against estimated slick drift speed.
        
        SEMANTIC RULE:
        - When vessel_sog_kn or drift_speed_kn is None (missing/unavailable evidence), returns neutral 0.5.
        - Provenance fields (observed_speed_kn) allow F5/F6 to distinguish missing evidence from actual measured SOG=0.0.
        - When vessel is stationary (vessel_sog_kn == 0.0), speed consistency is evaluated quantitatively against drift.
        """
        if vessel_sog_kn is None or drift_speed_kn is None or drift_speed_kn <= 0.0:
            return 0.5
        score = math.exp(-abs(vessel_sog_kn - drift_speed_kn) / 6.0)
        return round(max(0.0, min(1.0, score)), 4)

    def compute_course_compatibility(
        self,
        vessel_cog_deg: Optional[float],
        drift_course_deg: Optional[float],
    ) -> float:
        """Compares vessel movement heading against slick drift heading using circular angles.

        SEMANTIC RULE:
        - When vessel_cog_deg or drift_course_deg is None (missing/unavailable evidence), returns neutral 0.5.
        - Provenance fields (observed_course_deg) allow F5/F6 to distinguish missing evidence from actual COG=0.0 (due North).
        - When COG is measured (including 0.0), circular difference with 0°/360° wrap is evaluated.
        """
        if vessel_cog_deg is None or drift_course_deg is None:
            return 0.5
        d_theta = compute_circular_bearing_difference(vessel_cog_deg, drift_course_deg)
        dcos = math.cos(math.radians(d_theta))
        score = (dcos + 1.0) / 2.0
        return round(max(0.0, min(1.0, score)), 4)

    def compute_ais_gap_ratio_origin_window(
        self,
        track: VesselTrack,
        hypothesis: SourceHypothesisWindow,
        gap_threshold_hours: float = 1.0,
    ) -> float:
        """Calculates fraction of F3 origin window spent in an active AIS reporting dropout [0, 1].

        CRITICAL SEMANTIC RULE:
        - Only counts genuine reporting gaps between consecutive observed fixes (dt > threshold).
        - Does NOT count time before the vessel entered the area or after it left as gaps.
        - If the vessel has continuous reporting, gap ratio = 0.0.
        - If the vessel has no gaps or no coverage, gap ratio = 0.0 (absence != reporting gap).
        """
        obs_fixes = [f for f in track.fixes if f.is_observed]
        if len(obs_fixes) < 2:
            return 0.0

        t_start = parse_utc_timestamp(hypothesis.origin_time_start)
        t_end = parse_utc_timestamp(hypothesis.origin_time_end)
        w_sec = max(1.0, t_end.timestamp() - t_start.timestamp())

        gap_sec_in_window = 0.0
        for i in range(len(obs_fixes) - 1):
            fa = obs_fixes[i]
            fb = obs_fixes[i + 1]
            ta = fa.timestamp_utc if fa.timestamp_utc.tzinfo else fa.timestamp_utc.replace(tzinfo=timezone.utc)
            tb = fb.timestamp_utc if fb.timestamp_utc.tzinfo else fb.timestamp_utc.replace(tzinfo=timezone.utc)
            dt_h = max(0.0, (tb.timestamp() - ta.timestamp()) / 3600.0)

            if dt_h > gap_threshold_hours:
                # Intersect gap interval [ta, tb] with origin window [t_start, t_end]
                g_start = max(ta, t_start)
                g_end = min(tb, t_end)
                if g_end > g_start:
                    gap_sec_in_window += (g_end.timestamp() - g_start.timestamp())

        ratio = gap_sec_in_window / w_sec
        return round(max(0.0, min(1.0, ratio)), 4)

    def compute_track_overlap(
        self,
        track: VesselTrack,
        hypothesis: SourceHypothesisWindow,
    ) -> float:
        """Calculates temporal intersection between the vessel track and the F3 origin window.

        Formula:
            overlap = duration(track_interval ∩ origin_window) / duration(origin_window)
        """
        if not track.fixes:
            return 0.0

        t_start = parse_utc_timestamp(hypothesis.origin_time_start)
        t_end = parse_utc_timestamp(hypothesis.origin_time_end)
        w_sec = max(1.0, t_end.timestamp() - t_start.timestamp())

        t_first = track.fixes[0].timestamp_utc if track.fixes[0].timestamp_utc.tzinfo else track.fixes[0].timestamp_utc.replace(tzinfo=timezone.utc)
        t_last = track.fixes[-1].timestamp_utc if track.fixes[-1].timestamp_utc.tzinfo else track.fixes[-1].timestamp_utc.replace(tzinfo=timezone.utc)

        # Intersection interval
        inter_start = max(t_first, t_start)
        inter_end = min(t_last, t_end)

        if inter_end <= inter_start:
            # Single-fix track strictly inside window has instantaneous point presence
            if len(track.fixes) == 1 and (t_start <= t_first <= t_end):
                return round(min(1.0, 1.0 / max(1.0, w_sec / 3600.0)), 4)
            return 0.0

        inter_sec = inter_end.timestamp() - inter_start.timestamp()
        overlap = inter_sec / w_sec
        return round(max(0.0, min(1.0, overlap)), 4)
