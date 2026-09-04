"""Feature F4.4 — Closest Approach / Distance Analysis Service.

Determines a vessel's spatial relationship to an F3 SourceHypothesisWindow.
Calculates:
- distance_to_source_observed_km (observed transmissions only)
- distance_to_source_interpolated_km (interpolated / dead-reckoned positions only)
- distance_to_source_effective_km (minimum of observed and interpolated)
- closest_approach_is_interpolated flag (strictly preserving interpolation provenance)
- closest approach timestamps

Uses proper spherical geodesic distance (Haversine from F4.2).
Does NOT infer vessel responsibility or rank candidates.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple, Union

from shared.schemas.f3_contract import SourceHypothesisWindow
from backend.f4_ais.corridor import haversine_distance_km
from backend.f4_ais.schemas import (
    ClosestApproachResult,
    CorridorAISMatch,
    ValidatedAISFix,
    VesselTrack,
)


class DistanceAnalysisService:
    """Deterministic service for vessel track closest approach and distance analysis."""

    def analyze_track_distance(
        self,
        track: VesselTrack,
        hypothesis: SourceHypothesisWindow,
    ) -> ClosestApproachResult:
        """Calculates observed, interpolated, and effective closest approach to the source."""
        src_lat = hypothesis.source_location.lat
        src_lon = hypothesis.source_location.lon
        event_id = hypothesis.event_id
        hyp_id = hypothesis.source_hypothesis_id

        if not track.fixes:
            return ClosestApproachResult(
                mmsi=track.mmsi,
                track_id=track.track_id or f"TRK_{event_id}_{track.mmsi}",
                event_id=event_id,
                source_hypothesis_id=hyp_id,
                distance_to_source_observed_km=9999.0,
                distance_to_source_interpolated_km=9999.0,
                distance_to_source_effective_km=9999.0,
                closest_approach_is_interpolated=False,
                closest_approach_timestamp=None,
                interpolated_closest_timestamp=None,
            )

        min_obs_dist = float("inf")
        min_obs_ts: Optional[str] = None
        min_obs_sog: Optional[float] = None
        min_obs_cog: Optional[float] = None
        min_obs_lat: Optional[float] = None
        min_obs_lon: Optional[float] = None

        min_interp_dist = float("inf")
        min_interp_ts: Optional[str] = None
        min_interp_lat: Optional[float] = None
        min_interp_lon: Optional[float] = None

        for fix in track.fixes:
            dist_km = haversine_distance_km(fix.latitude, fix.longitude, src_lat, src_lon)
            if fix.is_observed:
                if dist_km < min_obs_dist:
                    min_obs_dist = dist_km
                    min_obs_ts = fix.timestamp_iso
                    min_obs_sog = fix.sog_kn
                    min_obs_cog = fix.cog_deg
                    min_obs_lat = fix.latitude
                    min_obs_lon = fix.longitude
            else:
                if dist_km < min_interp_dist:
                    min_interp_dist = dist_km
                    min_interp_ts = fix.timestamp_iso
                    min_interp_lat = fix.latitude
                    min_interp_lon = fix.longitude

        has_obs = min_obs_dist != float("inf")
        has_interp = min_interp_dist != float("inf")

        d_obs = round(min_obs_dist, 3) if has_obs else 9999.0
        d_interp = round(min_interp_dist, 3) if has_interp else 9999.0

        if has_obs and has_interp:
            d_eff = min(d_obs, d_interp)
            closest_is_interp = bool(d_interp < d_obs)
        elif has_obs:
            d_eff = d_obs
            closest_is_interp = False
        elif has_interp:
            d_eff = d_interp
            closest_is_interp = True
        else:
            d_eff = 9999.0
            closest_is_interp = False

        # Primary closest approach timestamp/position corresponds to the effective minimum
        primary_ts = min_interp_ts if closest_is_interp else min_obs_ts
        primary_lat = min_interp_lat if closest_is_interp else min_obs_lat
        primary_lon = min_interp_lon if closest_is_interp else min_obs_lon

        return ClosestApproachResult(
            mmsi=track.mmsi,
            track_id=track.track_id or f"TRK_{event_id}_{track.mmsi}",
            event_id=event_id,
            source_hypothesis_id=hyp_id,
            distance_to_source_observed_km=d_obs,
            distance_to_source_interpolated_km=d_interp,
            distance_to_source_effective_km=d_eff,
            closest_approach_is_interpolated=closest_is_interp,
            closest_approach_timestamp=primary_ts,
            interpolated_closest_timestamp=min_interp_ts,
            closest_observed_sog_kn=min_obs_sog,
            closest_observed_cog_deg=min_obs_cog,
            closest_approach_lat=primary_lat,
            closest_approach_lon=primary_lon,
        )

    def analyze_fleet_distance(
        self,
        tracks: Dict[str, VesselTrack],
        hypothesis: SourceHypothesisWindow,
    ) -> Dict[str, ClosestApproachResult]:
        """Calculates distance analysis for an entire fleet of vessel tracks."""
        results: Dict[str, ClosestApproachResult] = {}
        for key, trk in tracks.items():
            results[key] = self.analyze_track_distance(trk, hypothesis)
        return results
