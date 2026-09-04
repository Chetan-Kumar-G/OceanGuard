"""Deterministic specialist agents for Feature F4 (Historical AIS Reconstruction).

Agents act as modular orchestrators for deterministic data validation,
spatial-temporal filtering, track reconstruction, compatibility analysis,
and contract enforcement.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from shared.config.settings import get_settings
from shared.schemas.f3_contract import SourceHypothesisWindow
from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.schemas import (
    AISValidationReport,
    RawAISRecord,
    ValidatedAISFix,
    VesselTrack,
)
from backend.f4_ais.validation import parse_utc_timestamp, validate_ais_stream


from backend.f4_ais.ingestion import AISIngestionService


class AISIngestionAgent:
    """Agent responsible for ingesting, validating, and normalizing raw AIS streams."""

    def __init__(self, ingestion_service: Optional[AISIngestionService] = None) -> None:
        self.service = ingestion_service or AISIngestionService()

    def ingest_from_csv(
        self, csv_path: Optional[Path] = None, max_records: Optional[int] = None
    ) -> Tuple[List[ValidatedAISFix], AISValidationReport]:
        """Reads raw AIS transmissions from CSV, normalizes timestamps to UTC, and validates fields."""
        return self.service.ingest_csv(csv_path=csv_path, max_records=max_records)

    def ingest_records(
        self, records: Iterable[Union[Dict[str, Any], RawAISRecord]]
    ) -> Tuple[List[ValidatedAISFix], AISValidationReport]:
        """Validates and normalizes in-memory raw AIS records."""
        return self.service.ingest_records(records)


from backend.f4_ais.corridor import CorridorFilteringService
from backend.f4_ais.schemas import (
    AISValidationReport,
    CorridorAISMatch,
    CorridorFilterResult,
    RawAISRecord,
    ValidatedAISFix,
    VesselTrack,
)


class CorridorFilteringAgent:
    """Agent responsible for spatial and temporal AIS corridor filtering.
    
    Acts as the agent interface orchestrating CorridorFilteringService.
    Does NOT construct vessel tracks, calculate dark gaps, or generate CandidateVessel records.
    """

    def __init__(self, service: Optional[CorridorFilteringService] = None) -> None:
        self.service = service or CorridorFilteringService()

    def filter_corridor(
        self,
        fixes: Iterable[ValidatedAISFix],
        hypothesis: SourceHypothesisWindow,
    ) -> CorridorFilterResult:
        """Filters fixes strictly within the spatial uncertainty radius and origin time window."""
        return self.service.filter_corridor(fixes, hypothesis)

    def filter_multiple_hypotheses(
        self,
        fixes: Iterable[ValidatedAISFix],
        hypotheses: Sequence[SourceHypothesisWindow],
    ) -> Dict[str, CorridorFilterResult]:
        """Filters fixes independently against multiple competing source hypotheses."""
        return self.service.filter_multiple_hypotheses(fixes, hypotheses)

    def filter_fixes(
        self,
        fixes: Sequence[ValidatedAISFix],
        hypothesis: SourceHypothesisWindow,
        spatial_buffer_km: float = 200.0,
        temporal_buffer_hours: float = 36.0,
    ) -> List[ValidatedAISFix]:
        """Filters fixes roughly within the broad spatio-temporal corridor of the hypothesis.

        Applies preliminary coarse filtering to avoid processing irrelevant fleet transmissions.
        """
        if not fixes:
            return []

        t_start = parse_utc_timestamp(hypothesis.origin_time_start)
        t_end = parse_utc_timestamp(hypothesis.origin_time_end)

        # Expand temporal corridor
        t_lo_s = t_start.timestamp() - (temporal_buffer_hours * 3600.0)
        t_hi_s = t_end.timestamp() + (temporal_buffer_hours * 3600.0)

        filtered: List[ValidatedAISFix] = []
        for fix in fixes:
            ts = fix.timestamp_utc.timestamp()
            if t_lo_s <= ts <= t_hi_s:
                filtered.append(fix)

        return filtered

    def get_candidate_mmsis(
        self,
        fixes: Sequence[ValidatedAISFix],
    ) -> List[str]:
        """Extracts unique MMSIs from a set of filtered fixes."""
        return sorted(list(set(f.mmsi for f in fixes)))


CandidateFilteringAgent = CorridorFilteringAgent  # Backward-compatible alias for F4.0 foundation


from backend.f4_ais.track import TrackReconstructionService


class TrackReconstructionAgent:
    """Agent responsible for chronological ordering and grouping of vessel tracks."""

    def __init__(self, service: Optional[TrackReconstructionService] = None) -> None:
        self.service = service or TrackReconstructionService()

    def build_tracks(
        self,
        fixes: Sequence[Union[CorridorAISMatch, ValidatedAISFix]],
        event_id: Optional[str] = None,
        hypothesis_id: Optional[str] = None,
        gap_threshold_hours: Optional[float] = None,
    ) -> Dict[str, VesselTrack]:
        """Groups fixes by MMSI and reconstructs chronological tracks with gap metrics."""
        return self.service.build_tracks(
            fixes=fixes,
            event_id=event_id,
            hypothesis_id=hypothesis_id,
            gap_threshold_hours=gap_threshold_hours,
        )

    def build_tracks_from_corridor_matches(
        self,
        matches: Sequence[CorridorAISMatch],
        gap_threshold_hours: Optional[float] = None,
    ) -> Dict[str, VesselTrack]:
        """Groups CorridorAISMatch records into tracks by hypothesis and MMSI."""
        return self.service.build_tracks_from_corridor_matches(
            matches=matches,
            gap_threshold_hours=gap_threshold_hours,
        )


from backend.f4_ais.compatibility import (
    CompatibilityAnalysisService,
    compute_circular_bearing_difference,
)


class CompatibilityAnalysisAgent:
    """Agent responsible for calculating transparent spatio-temporal compatibility features.

    NEVER produces guilt, culpability, or responsibility probabilities.
    """

    def __init__(self, service: Optional[CompatibilityAnalysisService] = None) -> None:
        self.service = service or CompatibilityAnalysisService()

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
        """Calculates physical, temporal, and navigational compatibility evidence signals."""
        return self.service.analyze_compatibility(
            track=track,
            hypothesis=hypothesis,
            closest_approach=closest_approach,
            dark_gap=dark_gap,
            drift_speed_kn=drift_speed_kn,
            drift_course_deg=drift_course_deg,
            gap_threshold_hours=gap_threshold_hours,
        )

    def analyze_empty_track(
        self,
        mmsi: str,
        hypothesis: SourceHypothesisWindow,
    ) -> Dict[str, Any]:
        """Produces a neutral compatibility payload when no fixes exist for an MMSI."""
        return {
            "distance_to_source_effective_km": 9999.0,
            "temporal_compatibility": 0.0,
            "track_overlap": 0.0,
            "track_completeness": 0.0,
            "dark_gap_over_source": False,
            "dark_gap_over_source_hours": 0.0,
            "closest_approach_is_interpolated": False,
            "speed_compatibility": 0.0,
            "course_compatibility": 0.0,
            "ais_gap_ratio_origin_window": 1.0,
        }


class ProvenanceContractAgent:
    """Agent responsible for assembling and validating the frozen CandidateVessel contract."""

    @staticmethod
    def format_track_id(event_id: str, mmsi: str) -> str:
        """Enforces the frozen Track ID convention: TRK_<event_id>_<mmsi>."""
        return f"TRK_{event_id}_{mmsi}"

    def assemble_candidate(
        self,
        event_id: str,
        mmsi: str,
        hypothesis_id: str,
        compatibility: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> CandidateVessel:
        """Constructs and validates a CandidateVessel instance.

        Guarantees strict quarantine of any QA or evaluation fields.
        """
        track_id = self.format_track_id(event_id, mmsi)
        prov = provenance or {}

        payload: Dict[str, Any] = {
            "track_id": track_id,
            "event_id": event_id,
            "mmsi": str(mmsi),
            "source_hypothesis_id": hypothesis_id,
            "distance_to_source_effective_km": float(compatibility["distance_to_source_effective_km"]),
            "temporal_compatibility": float(compatibility["temporal_compatibility"]),
            "track_overlap": float(compatibility["track_overlap"]),
            "track_completeness": float(compatibility["track_completeness"]),
            "dark_gap_over_source": bool(compatibility["dark_gap_over_source"]),
            "dark_gap_over_source_hours": float(compatibility.get("dark_gap_over_source_hours", 0.0)),
            "closest_approach_is_interpolated": bool(compatibility["closest_approach_is_interpolated"]),
            "speed_compatibility": float(compatibility.get("speed_compatibility", 0.5)),
            "course_compatibility": float(compatibility.get("course_compatibility", 0.5)),
            "ais_gap_ratio_origin_window": float(compatibility.get("ais_gap_ratio_origin_window", 1.0)),
            # Provenance fields
            "vessel_type": prov.get("vessel_type"),
            "vessel_length": prov.get("vessel_length"),
            "vessel_width": prov.get("vessel_width"),
            "draught": prov.get("draught"),
            "first_timestamp": prov.get("first_timestamp"),
            "last_timestamp": prov.get("last_timestamp"),
            "track_duration_h": prov.get("track_duration_h"),
            "number_of_observations": prov.get("number_of_observations"),
            "gap_count": prov.get("gap_count"),
            "max_gap_hours": prov.get("max_gap_hours"),
            "distance_to_source_km": prov.get("distance_to_source_km"),
            "distance_to_source_interpolated_km": prov.get("distance_to_source_interpolated_km"),
            "closest_approach_timestamp": prov.get("closest_approach_timestamp"),
            "interpolated_closest_timestamp": prov.get("interpolated_closest_timestamp"),
            "observed_speed_kn": prov.get("observed_speed_kn"),
            "observed_course_deg": prov.get("observed_course_deg"),
            "slick_drift_speed_kn": prov.get("slick_drift_speed_kn"),
            "slick_drift_course_deg": prov.get("slick_drift_course_deg"),
        }

        # Validate against the frozen Pydantic contract
        return CandidateVessel.model_validate(payload)
