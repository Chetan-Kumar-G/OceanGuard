"""Feature F4.5 — AIS Gap / Dark-Gap Analysis Service.

Determines whether AIS reporting dropouts/gaps occurred near the F3 source location
during the source hypothesis origin time window.

CRITICAL SAFETY PRINCIPLE:
A dark gap is an objective AIS transmission evidence signal.
It is NEVER an inference of guilt, proof of culpability, or accusation of wrongdoing.
Attribution belongs strictly to multi-source evidence fusion in F5/F6.

Differentiates:
- Normal continuous reporting (cadence <= gap threshold)
- General reporting gap elsewhere in time/space
- Dark gap intersecting the F3 source window and region
- Empty AIS coverage (zero transmissions)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from shared.schemas.f3_contract import SourceHypothesisWindow
from backend.f4_ais.corridor import haversine_distance_km
from backend.f4_ais.schemas import (
    AISGapInterval,
    DarkGapResult,
    ValidatedAISFix,
    VesselTrack,
)
from backend.f4_ais.validation import parse_utc_timestamp


# [UNRESOLVED] Default reporting gap threshold.
# Maritime Class A standard reporting interval underway is 2-10s; Class B / satellite is several minutes.
# If no per-vessel cadence is specified, 1.0 hour is the established forensic standard.
DEFAULT_GAP_THRESHOLD_HOURS: float = 1.0


class DarkGapAnalysisService:
    """Deterministic domain service for AIS reporting gap and dark-gap detection."""

    def __init__(self, default_gap_threshold_hours: float = DEFAULT_GAP_THRESHOLD_HOURS) -> None:
        self.default_gap_threshold_hours = default_gap_threshold_hours

    def analyze_dark_gap(
        self,
        track: VesselTrack,
        hypothesis: SourceHypothesisWindow,
        gap_threshold_hours: Optional[float] = None,
    ) -> DarkGapResult:
        """Evaluates whether a vessel track exhibits an AIS dropout over the source hypothesis."""
        threshold = gap_threshold_hours if gap_threshold_hours is not None else self.default_gap_threshold_hours
        event_id = hypothesis.event_id
        hyp_id = hypothesis.source_hypothesis_id
        src_lat = hypothesis.source_location.lat
        src_lon = hypothesis.source_location.lon
        radius_km = hypothesis.uncertainty_radius_km

        t_start = parse_utc_timestamp(hypothesis.origin_time_start)
        t_end = parse_utc_timestamp(hypothesis.origin_time_end)

        # Consider only observed transmissions to detect true reporting gaps
        obs_fixes = [f for f in track.fixes if f.is_observed]

        if len(obs_fixes) < 2:
            return DarkGapResult(
                mmsi=track.mmsi,
                track_id=track.track_id or f"TRK_{event_id}_{track.mmsi}",
                event_id=event_id,
                source_hypothesis_id=hyp_id,
                dark_gap_over_source=False,
                dark_gap_over_source_hours=0.0,
                total_gaps=0,
                max_gap_hours=0.0,
                gap_intervals=[],
            )

        gap_intervals: List[AISGapInterval] = []
        dark_gap_over_source = False
        dark_gap_over_source_hours = 0.0
        max_gap_hours = 0.0

        for i in range(len(obs_fixes) - 1):
            f_prev = obs_fixes[i]
            f_next = obs_fixes[i + 1]

            t_a = f_prev.timestamp_utc if f_prev.timestamp_utc.tzinfo else f_prev.timestamp_utc.replace(tzinfo=timezone.utc)
            t_b = f_next.timestamp_utc if f_next.timestamp_utc.tzinfo else f_next.timestamp_utc.replace(tzinfo=timezone.utc)
            duration_h = max(0.0, (t_b.timestamp() - t_a.timestamp()) / 3600.0)

            if duration_h > threshold:
                max_gap_hours = max(max_gap_hours, duration_h)

                # Check temporal overlap with origin window [t_start, t_end]
                o_a = max(t_a, t_start)
                o_b = min(t_b, t_end)
                overlaps_origin = bool(o_b > o_a)
                overlap_h = max(0.0, (o_b.timestamp() - o_a.timestamp()) / 3600.0) if overlaps_origin else 0.0

                # Check spatial proximity across gap segment
                is_over_source = self._segment_passes_near_source(
                    lat1=f_prev.latitude,
                    lon1=f_prev.longitude,
                    lat2=f_next.latitude,
                    lon2=f_next.longitude,
                    src_lat=src_lat,
                    src_lon=src_lon,
                    radius_km=radius_km,
                )

                if overlaps_origin and is_over_source:
                    dark_gap_over_source = True
                    dark_gap_over_source_hours = max(dark_gap_over_source_hours, overlap_h)

                gap_intervals.append(
                    AISGapInterval(
                        start_timestamp=f_prev.timestamp_iso,
                        end_timestamp=f_next.timestamp_iso,
                        duration_hours=round(duration_h, 3),
                        start_lat=f_prev.latitude,
                        start_lon=f_prev.longitude,
                        end_lat=f_next.latitude,
                        end_lon=f_next.longitude,
                        overlaps_origin_window=overlaps_origin,
                        is_over_source=is_over_source,
                        overlap_hours=round(overlap_h, 3),
                    )
                )

        return DarkGapResult(
            mmsi=track.mmsi,
            track_id=track.track_id or f"TRK_{event_id}_{track.mmsi}",
            event_id=event_id,
            source_hypothesis_id=hyp_id,
            dark_gap_over_source=dark_gap_over_source,
            dark_gap_over_source_hours=round(dark_gap_over_source_hours, 3),
            total_gaps=len(gap_intervals),
            max_gap_hours=round(max_gap_hours, 3),
            gap_intervals=gap_intervals,
        )

    def _segment_passes_near_source(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        src_lat: float,
        src_lon: float,
        radius_km: float,
        num_samples: int = 11,
    ) -> bool:
        """Determines if any sampled position along a gap segment falls within the source radius."""
        d1 = haversine_distance_km(lat1, lon1, src_lat, src_lon)
        d2 = haversine_distance_km(lat2, lon2, src_lat, src_lon)
        if d1 <= radius_km or d2 <= radius_km:
            return True

        # Sample intermediate positions along linear segment
        for step in range(1, num_samples - 1):
            frac = step / float(num_samples - 1)
            interp_lat = lat1 + frac * (lat2 - lat1)
            interp_lon = lon1 + frac * (lon2 - lon1)
            d_mid = haversine_distance_km(interp_lat, interp_lon, src_lat, src_lon)
            if d_mid <= radius_km:
                return True

        return False
