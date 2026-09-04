"""Deterministic spatio-temporal corridor filtering service for Feature F4.2.

Correlates global historical AIS transmissions (ValidatedAISFix) against F3 SourceHypothesisWindow
definitions using geodesic distance (Haversine) and UTC origin-time windows.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from shared.schemas.f3_contract import SourceHypothesisWindow
from backend.f4_ais.schemas import CorridorAISMatch, CorridorFilterResult, ValidatedAISFix
from backend.f4_ais.validation import parse_utc_timestamp

_EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes the great-circle distance between two points on Earth using the Haversine formula.

    Args:
        lat1: Latitude of point 1 in degrees [-90.0, 90.0]
        lon1: Longitude of point 1 in degrees [-180.0, 180.0]
        lat2: Latitude of point 2 in degrees [-90.0, 90.0]
        lon2: Longitude of point 2 in degrees [-180.0, 180.0]

    Returns:
        Geodesic distance in kilometers (>= 0.0)
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    # Clamp to [0.0, 1.0] to prevent math domain error from floating-point rounding
    a_clamped = max(0.0, min(1.0, a))
    c = 2.0 * math.asin(math.sqrt(a_clamped))
    return _EARTH_RADIUS_KM * c


def is_spatially_compatible(
    fix_lat: float,
    fix_lon: float,
    src_lat: float,
    src_lon: float,
    uncertainty_radius_km: float,
) -> Tuple[bool, float]:
    """Evaluates whether an AIS fix falls within the hypothesis uncertainty radius.

    Required rule:
        distance_to_source_km <= uncertainty_radius_km -> INCLUDE
        distance_to_source_km > uncertainty_radius_km  -> EXCLUDE

    Returns:
        Tuple of (is_compatible: bool, distance_km: float)
    """
    dist_km = haversine_distance_km(fix_lat, fix_lon, src_lat, src_lon)
    return (dist_km <= uncertainty_radius_km), dist_km


def is_temporally_compatible(
    ts_utc: datetime,
    t_start_utc: datetime,
    t_end_utc: datetime,
) -> bool:
    """Evaluates whether an AIS fix timestamp falls within the origin time window.

    Boundary behavior: t_start_utc <= ts_utc <= t_end_utc is INCLUDED (both endpoints inclusive).
    Normalizes all datetimes to UTC timezone-aware comparisons.
    """
    if ts_utc.tzinfo is None:
        t_check = ts_utc.replace(tzinfo=timezone.utc)
    else:
        t_check = ts_utc.astimezone(timezone.utc)

    if t_start_utc.tzinfo is None:
        t_start = t_start_utc.replace(tzinfo=timezone.utc)
    else:
        t_start = t_start_utc.astimezone(timezone.utc)

    if t_end_utc.tzinfo is None:
        t_end = t_end_utc.replace(tzinfo=timezone.utc)
    else:
        t_end = t_end_utc.astimezone(timezone.utc)

    return t_start <= t_check <= t_end


class CorridorFilteringService:
    """Deterministic service for spatial and temporal corridor filtering of AIS transmissions."""

    def filter_corridor(
        self,
        fixes: Iterable[ValidatedAISFix],
        hypothesis: SourceHypothesisWindow,
    ) -> CorridorFilterResult:
        """Filters a stream of ValidatedAISFix records against a single SourceHypothesisWindow.

        Both spatial and temporal constraints must be satisfied for a corridor match.
        Spatial matches, temporal matches, and joint matches are tracked deterministically.
        """
        event_id = hypothesis.event_id
        hyp_id = hypothesis.source_hypothesis_id
        src_lat = hypothesis.source_location.lat
        src_lon = hypothesis.source_location.lon
        radius_km = hypothesis.uncertainty_radius_km
        t_start = parse_utc_timestamp(hypothesis.origin_time_start)
        t_end = parse_utc_timestamp(hypothesis.origin_time_end)

        total_input = 0
        spatial_count = 0
        temporal_count = 0
        matches: List[CorridorAISMatch] = []

        for fix in fixes:
            total_input += 1
            is_space, dist_km = is_spatially_compatible(
                fix.latitude, fix.longitude, src_lat, src_lon, radius_km
            )
            is_time = is_temporally_compatible(fix.timestamp_utc, t_start, t_end)

            if is_space:
                spatial_count += 1
            if is_time:
                temporal_count += 1

            if is_space and is_time:
                ts_utc = fix.timestamp_utc
                if ts_utc.tzinfo is None:
                    ts_utc = ts_utc.replace(tzinfo=timezone.utc)
                else:
                    ts_utc = ts_utc.astimezone(timezone.utc)

                match = CorridorAISMatch(
                    event_id=event_id,
                    source_hypothesis_id=hyp_id,
                    mmsi=fix.mmsi,
                    timestamp_utc=ts_utc,
                    timestamp_iso=fix.timestamp_iso,
                    latitude=fix.latitude,
                    longitude=fix.longitude,
                    distance_to_source_km=round(dist_km, 4),
                    sog_kn=fix.sog_kn,
                    cog_deg=fix.cog_deg,
                    heading_deg=fix.heading_deg,
                    nav_status=fix.nav_status,
                    vessel_type=fix.vessel_type,
                    vessel_length=fix.vessel_length,
                    vessel_width=fix.vessel_width,
                    draught=fix.draught,
                    source=fix.source,
                    is_observed=fix.is_observed,
                    sim_hours=fix.sim_hours,
                )
                matches.append(match)

        # Stable deterministic sorting: (event_id, source_hypothesis_id, mmsi, timestamp_iso)
        matches.sort(key=lambda m: (m.event_id, m.source_hypothesis_id, m.mmsi, m.timestamp_iso))

        return CorridorFilterResult(
            event_id=event_id,
            source_hypothesis_id=hyp_id,
            total_ais_input=total_input,
            spatial_matches=spatial_count,
            temporal_matches=temporal_count,
            corridor_matches=len(matches),
            matches=matches,
        )

    def filter_multiple_hypotheses(
        self,
        fixes: Iterable[ValidatedAISFix],
        hypotheses: Sequence[SourceHypothesisWindow],
    ) -> Dict[str, CorridorFilterResult]:
        """Evaluates AIS records independently against multiple competing source hypotheses.

        If a fix satisfies multiple hypotheses, distinct CorridorAISMatch records are preserved
        for each hypothesis without deduplicating or losing source_hypothesis_id association.
        """
        fix_list = list(fixes) if not isinstance(fixes, list) else fixes
        results: Dict[str, CorridorFilterResult] = {}

        for hyp in hypotheses:
            res = self.filter_corridor(fix_list, hyp)
            results[hyp.source_hypothesis_id] = res

        return results
